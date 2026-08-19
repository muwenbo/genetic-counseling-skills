#!/usr/bin/env python3
"""Inspect and filter a large annotated germline callset without dependencies.

The script is deliberately non-interpretive. It reads annotated VCF, TSV, CSV, or
XLSX callsets locally, reports the annotation fields it can see, and applies only
the reviewer-approved deterministic filters. It never contacts the network, never
adds annotations that are not already in the file, and never prints identifiers or
raw genotype-bearing rows to stdout.

Two subcommands mirror the review-variant-table workflow:

    inspect  Report format, variant count, chromosome coverage, sample columns,
             and candidate annotation fields. Proposes; never selects.

    filter   Apply reviewer-chosen thresholds and emit a variant_prioritization
             JSON with a stage-by-stage funnel and excluded-class counts.

Annotations only ever come from the file itself (INFO keys, VEP CSQ / SnpEff ANN
subfields, or table columns). A variant with no frequency annotation is reported
as unknown frequency, never treated as rare or common by default.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import re
import sys
import zipfile
from pathlib import Path
from typing import Any, Iterator
from xml.etree import ElementTree as ET


VERSION = "0.1.0"
MAX_FILE_BYTES = 2 * 1024 * 1024 * 1024  # 2 GiB guard
MAX_INSPECT_ROWS = 5_000_000

SHEET_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"

# Ordered most-to-least severe. Used only when the reviewer asks the script to
# filter by a severity tier rather than an explicit term set.
CONSEQUENCE_SEVERITY = [
    "transcript_ablation",
    "splice_acceptor_variant",
    "splice_donor_variant",
    "stop_gained",
    "frameshift_variant",
    "stop_lost",
    "start_lost",
    "transcript_amplification",
    "inframe_insertion",
    "inframe_deletion",
    "missense_variant",
    "protein_altering_variant",
    "splice_region_variant",
    "incomplete_terminal_codon_variant",
    "start_retained_variant",
    "stop_retained_variant",
    "synonymous_variant",
    "coding_sequence_variant",
    "mature_miRNA_variant",
    "5_prime_UTR_variant",
    "3_prime_UTR_variant",
    "non_coding_transcript_exon_variant",
    "intron_variant",
    "NMD_transcript_variant",
    "non_coding_transcript_variant",
    "upstream_gene_variant",
    "downstream_gene_variant",
    "TFBS_ablation",
    "TFBS_amplification",
    "TF_binding_site_variant",
    "regulatory_region_ablation",
    "regulatory_region_amplification",
    "feature_elongation",
    "regulatory_region_variant",
    "feature_truncation",
    "intergenic_variant",
]
_SEVERITY_RANK = {term: i for i, term in enumerate(CONSEQUENCE_SEVERITY)}


class ReviewError(Exception):
    """Raised for conditions that must stop the run rather than guess."""


# --------------------------------------------------------------------------- #
# Format detection and low-level readers
# --------------------------------------------------------------------------- #

def _guard_size(path: Path) -> None:
    size = path.stat().st_size
    if size > MAX_FILE_BYTES:
        raise ReviewError(f"file exceeds {MAX_FILE_BYTES} byte guard: {size}")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def detect_format(path: Path) -> str:
    name = path.name.lower()
    if name.endswith(".vcf") or name.endswith(".vcf.gz") or name.endswith(".vcf.bgz"):
        return "vcf"
    if name.endswith(".xlsx"):
        return "xlsx"
    if name.endswith(".tsv") or name.endswith(".tsv.gz"):
        return "tsv"
    if name.endswith(".csv") or name.endswith(".csv.gz"):
        return "csv"
    # Sniff: gzip magic then peek, else look for a VCF header line.
    with path.open("rb") as handle:
        head = handle.read(4)
    opener = gzip.open if head[:2] == b"\x1f\x8b" else open
    with opener(path, "rt", encoding="utf-8", errors="replace") as handle:  # type: ignore[operator]
        first = handle.readline()
    if first.startswith("##fileformat=VCF") or first.startswith("#CHROM"):
        return "vcf"
    if "\t" in first:
        return "tsv"
    if "," in first:
        return "csv"
    raise ReviewError("could not detect VCF/TSV/CSV/XLSX format; pass an explicit file")


def _open_text(path: Path) -> io.TextIOBase:
    with path.open("rb") as handle:
        magic = handle.read(2)
    if magic == b"\x1f\x8b":
        return gzip.open(path, "rt", encoding="utf-8", errors="replace")  # type: ignore[return-value]
    return path.open("rt", encoding="utf-8", errors="replace")


# ---- XLSX (first or selected sheet, header + rows) ------------------------ #

def _xlsx_shared_strings(zf: zipfile.ZipFile) -> list[str]:
    try:
        data = zf.read("xl/sharedStrings.xml")
    except KeyError:
        return []
    strings: list[str] = []
    root = ET.fromstring(data)
    for si in root.findall(f"{{{SHEET_NS}}}si"):
        parts = [node.text or "" for node in si.iter(f"{{{SHEET_NS}}}t")]
        strings.append("".join(parts))
    return strings


def _xlsx_sheet_target(zf: zipfile.ZipFile, sheet_index: int) -> str:
    root = ET.fromstring(zf.read("xl/workbook.xml"))
    sheets = root.find(f"{{{SHEET_NS}}}sheets")
    if sheets is None:
        raise ReviewError("workbook has no sheets")
    names = list(sheets)
    if not (0 <= sheet_index < len(names)):
        raise ReviewError(f"sheet_index {sheet_index} out of range (0..{len(names)-1})")
    rid = names[sheet_index].get(
        "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
    )
    rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
    for rel in rels:
        if rel.get("Id") == rid:
            target = rel.get("Target", "")
            return "xl/" + target.lstrip("/") if not target.startswith("xl/") else target
    # Fall back to positional worksheet file.
    return f"xl/worksheets/sheet{sheet_index + 1}.xml"


def _col_to_index(ref: str) -> int:
    letters = re.match(r"[A-Z]+", ref or "")
    if not letters:
        return 0
    idx = 0
    for ch in letters.group(0):
        idx = idx * 26 + (ord(ch) - ord("A") + 1)
    return idx - 1


def _iter_xlsx_rows(path: Path, sheet_index: int) -> Iterator[list[str]]:
    with zipfile.ZipFile(path) as zf:
        strings = _xlsx_shared_strings(zf)
        target = _xlsx_sheet_target(zf, sheet_index)
        with zf.open(target) as sheet:
            for _event, elem in ET.iterparse(sheet, events=("end",)):
                if elem.tag != f"{{{SHEET_NS}}}row":
                    continue
                cells: dict[int, str] = {}
                for c in elem.findall(f"{{{SHEET_NS}}}c"):
                    col = _col_to_index(c.get("r", ""))
                    ctype = c.get("t")
                    v = c.find(f"{{{SHEET_NS}}}v")
                    inline = c.find(f"{{{SHEET_NS}}}is")
                    if ctype == "s" and v is not None and v.text is not None:
                        val = strings[int(v.text)] if int(v.text) < len(strings) else ""
                    elif ctype == "inlineStr" and inline is not None:
                        val = "".join(t.text or "" for t in inline.iter(f"{{{SHEET_NS}}}t"))
                    elif v is not None:
                        val = v.text or ""
                    else:
                        val = ""
                    cells[col] = val
                if cells:
                    width = max(cells) + 1
                    yield [cells.get(i, "") for i in range(width)]
                else:
                    yield []
                elem.clear()


# --------------------------------------------------------------------------- #
# Record iteration: a common dict-per-variant shape across all formats
# --------------------------------------------------------------------------- #

def _parse_vcf_meta(path: Path) -> tuple[dict[str, str], list[str], list[str]]:
    """Return (info_descriptions, csq_subfields, sample_names)."""
    info_desc: dict[str, str] = {}
    csq_fields: list[str] = []
    samples: list[str] = []
    with _open_text(path) as handle:
        for line in handle:
            if line.startswith("##INFO="):
                mid = re.search(r"ID=([^,>]+)", line)
                mdesc = re.search(r'Description="([^"]*)"', line)
                if mid:
                    info_desc[mid.group(1)] = mdesc.group(1) if mdesc else ""
                    if mid.group(1) in ("CSQ", "ANN", "vep") and mdesc:
                        fmt = re.search(r"Format:\s*([^\"]+)", mdesc.group(1))
                        if fmt:
                            csq_fields = [
                                f.strip() for f in re.split(r"[|]", fmt.group(1)) if f.strip()
                            ]
            elif line.startswith("#CHROM"):
                cols = line.rstrip("\n").split("\t")
                if len(cols) > 9:
                    samples = cols[9:]
                break
            elif not line.startswith("#"):
                break
    return info_desc, csq_fields, samples


def _split_info(info: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for token in info.split(";"):
        if not token:
            continue
        if "=" in token:
            k, v = token.split("=", 1)
            out[k] = v
        else:
            out[token] = "true"
    return out


def iter_vcf_records(path: Path) -> Iterator[dict[str, Any]]:
    _info_desc, csq_fields, samples = _parse_vcf_meta(path)
    with _open_text(path) as handle:
        for line in handle:
            if line.startswith("#"):
                continue
            cols = line.rstrip("\n").split("\t")
            if len(cols) < 8:
                continue
            info = _split_info(cols[7])
            rec: dict[str, Any] = {
                "chrom": cols[0],
                "pos": cols[1],
                "ref": cols[3],
                "alt": cols[4],
                "qual": cols[5],
                "vcf_filter": cols[6],
                "info": info,
                "csq_fields": csq_fields,
            }
            # First-sample genotype (candidate zygosity only; no phasing inferred).
            if len(cols) > 9 and samples:
                fmt = cols[8].split(":")
                values = cols[9].split(":")
                gt_idx = fmt.index("GT") if "GT" in fmt else -1
                dp_idx = fmt.index("DP") if "DP" in fmt else -1
                rec["gt"] = values[gt_idx] if 0 <= gt_idx < len(values) else ""
                rec["fmt_dp"] = values[dp_idx] if 0 <= dp_idx < len(values) else ""
            yield rec


def _iter_delimited_rows(path: Path, fmt: str) -> Iterator[list[str]]:
    delimiter = "\t" if fmt == "tsv" else ","
    with _open_text(path) as handle:
        reader = csv.reader(handle, delimiter=delimiter)
        for row in reader:
            yield row


def iter_table_records(
    rows: Iterator[list[str]], header_row: int
) -> tuple[list[str], Iterator[dict[str, Any]]]:
    header: list[str] = []
    for i, row in enumerate(rows):
        if i == header_row:
            header = [c.strip() for c in row]
            break
    if not header:
        raise ReviewError("header row not found")

    def _gen() -> Iterator[dict[str, Any]]:
        for row in rows:
            if not any(cell.strip() for cell in row):
                continue
            rec = {header[i]: (row[i] if i < len(row) else "") for i in range(len(header))}
            yield {"columns": rec}

    return header, _gen()


# --------------------------------------------------------------------------- #
# Field access helpers (annotations only from the file)
# --------------------------------------------------------------------------- #

def _csq_values(rec: dict[str, Any], subfield: str) -> list[str]:
    info = rec.get("info", {})
    fields = rec.get("csq_fields", [])
    if subfield not in fields:
        return []
    idx = fields.index(subfield)
    raw = info.get("CSQ") or info.get("ANN") or ""
    out: list[str] = []
    for entry in raw.split(","):
        parts = entry.split("|")
        if idx < len(parts) and parts[idx]:
            out.append(parts[idx])
    return out


def get_field(rec: dict[str, Any], spec: str) -> str | None:
    """Resolve a field spec against a record.

    Spec forms:
      INFO/<key>     VCF INFO key
      CSQ/<subfield> VEP CSQ / SnpEff ANN subfield (first non-empty)
      COL/<name>     table column
      QUAL, FILTER, GT, FORMAT_DP   VCF fixed fields
    """
    if spec in ("QUAL",):
        return rec.get("qual")
    if spec in ("FILTER",):
        return rec.get("vcf_filter")
    if spec in ("GT",):
        return rec.get("gt")
    if spec in ("FORMAT_DP",):
        return rec.get("fmt_dp")
    if spec.startswith("INFO/"):
        return rec.get("info", {}).get(spec[5:])
    if spec.startswith("CSQ/"):
        vals = _csq_values(rec, spec[4:])
        return vals[0] if vals else None
    if spec.startswith("COL/"):
        return rec.get("columns", {}).get(spec[4:])
    return rec.get("columns", {}).get(spec)


def _max_float(raw: str | None) -> float | None:
    """Parse the maximum numeric value from a possibly &-joined AF annotation."""
    if raw is None or raw == "" or raw == ".":
        return None
    best: float | None = None
    for token in re.split(r"[&,|]", str(raw)):
        token = token.strip()
        if not token or token == ".":
            continue
        try:
            val = float(token)
        except ValueError:
            continue
        best = val if best is None else max(best, val)
    return best


def _consequence_terms(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [t.strip() for t in re.split(r"[&,;]", str(raw)) if t.strip()]


# --------------------------------------------------------------------------- #
# inspect
# --------------------------------------------------------------------------- #

FIELD_HINTS = {
    "af": re.compile(r"(gnomad|popmax|_af$|^af$|1000g|exac|maxaf|frequency)", re.I),
    "consequence": re.compile(r"(consequence|effect|annotation|func|impact)", re.I),
    "gene": re.compile(r"(gene|symbol)", re.I),
    "clinvar": re.compile(r"clinvar", re.I),
    "quality": re.compile(r"(^qual$|quality)", re.I),
    "depth": re.compile(r"(^dp$|depth)", re.I),
}


def cmd_inspect(args: argparse.Namespace) -> dict[str, Any]:
    path = Path(args.input)
    _guard_size(path)
    fmt = args.format or detect_format(path)
    report: dict[str, Any] = {
        "version": VERSION,
        "file_sha256": file_sha256(path),
        "format": fmt,
        "variant_count": 0,
        "chromosomes": {},
        "samples": [],
        "candidate_fields": {k: [] for k in FIELD_HINTS},
        "notes": [],
    }

    if fmt == "vcf":
        info_desc, csq_fields, samples = _parse_vcf_meta(path)
        report["samples"] = samples
        report["csq_subfields"] = csq_fields
        for key in info_desc:
            for role, pattern in FIELD_HINTS.items():
                if pattern.search(key):
                    report["candidate_fields"][role].append(f"INFO/{key}")
        for sub in csq_fields:
            for role, pattern in FIELD_HINTS.items():
                if pattern.search(sub):
                    report["candidate_fields"][role].append(f"CSQ/{sub}")
        chroms: dict[str, int] = {}
        count = 0
        for rec in iter_vcf_records(path):
            count += 1
            chroms[rec["chrom"]] = chroms.get(rec["chrom"], 0) + 1
            if count >= MAX_INSPECT_ROWS:
                report["notes"].append("variant count capped at inspection limit")
                break
        report["variant_count"] = count
        report["chromosomes"] = chroms
    else:
        if fmt == "xlsx":
            rows = list(_iter_xlsx_rows(path, args.sheet_index))
            header_row = args.header_row
            header = [c.strip() for c in rows[header_row]] if header_row < len(rows) else []
            data_rows = rows[header_row + 1 :]
        else:
            all_rows = list(_iter_delimited_rows(path, fmt))
            header_row = args.header_row
            header = [c.strip() for c in all_rows[header_row]] if header_row < len(all_rows) else []
            data_rows = all_rows[header_row + 1 :]
        report["header"] = header
        for col in header:
            for role, pattern in FIELD_HINTS.items():
                if pattern.search(col):
                    report["candidate_fields"][role].append(f"COL/{col}")
        chroms = {}
        count = 0
        chrom_idx = next((i for i, c in enumerate(header) if re.search(r"chrom|^chr$", c, re.I)), None)
        for row in data_rows:
            if not any(cell.strip() for cell in row):
                continue
            count += 1
            if chrom_idx is not None and chrom_idx < len(row):
                key = row[chrom_idx]
                chroms[key] = chroms.get(key, 0) + 1
        report["variant_count"] = count
        report["chromosomes"] = chroms

    for role in report["candidate_fields"]:
        report["candidate_fields"][role] = sorted(set(report["candidate_fields"][role]))
    if not any(report["candidate_fields"]["af"]):
        report["notes"].append(
            "no frequency annotation detected; AF-based filtering is not possible on this file"
        )
    return report


# --------------------------------------------------------------------------- #
# filter
# --------------------------------------------------------------------------- #

def _records(path: Path, fmt: str, params: dict[str, Any]) -> Iterator[dict[str, Any]]:
    if fmt == "vcf":
        yield from iter_vcf_records(path)
    elif fmt == "xlsx":
        rows = iter(_iter_xlsx_rows(path, params.get("sheet_index", 0)))
        _header, gen = iter_table_records(rows, params.get("header_row", 0))
        yield from gen
    else:
        rows = _iter_delimited_rows(path, fmt)
        _header, gen = iter_table_records(rows, params.get("header_row", 0))
        yield from gen


def _passes_consequence(rec: dict[str, Any], params: dict[str, Any]) -> bool | None:
    field = params.get("consequence_field")
    if not field:
        return None
    include = params.get("consequence_include")
    tier = params.get("consequence_max_rank")
    raw = get_field(rec, field)
    terms = _consequence_terms(raw)
    if not terms:
        return False  # annotation present as a filter but variant has none -> excluded
    if include:
        include_set = set(include)
        return any(t in include_set for t in terms)
    if tier is not None:
        return any(_SEVERITY_RANK.get(t, 10_000) <= tier for t in terms)
    return True


def cmd_filter(args: argparse.Namespace) -> dict[str, Any]:
    path = Path(args.input)
    _guard_size(path)
    params = json.loads(Path(args.params).read_text(encoding="utf-8"))
    fmt = params.get("format") or detect_format(path)
    build = params.get("genome_build")
    if not build:
        raise ReviewError("params.genome_build is required")

    af_field = params.get("af_field")
    af_max = params.get("af_max")
    keep_unknown_af = params.get("keep_unknown_af", True)
    gene_field = params.get("gene_field")
    gene_allowlist = set(params.get("gene_allowlist") or [])
    qual_field = params.get("quality_field")
    qual_min = params.get("quality_min")
    depth_field = params.get("depth_field")
    depth_min = params.get("depth_min")
    zygosity = params.get("require_zygosity")  # "hom" | "het" | None
    limit = params.get("limit", 500)

    funnel = {
        "examined": 0,
        "after_consequence": 0,
        "after_frequency": 0,
        "after_gene": 0,
        "after_quality": 0,
        "after_zygosity": 0,
        "shortlisted": 0,
    }
    excluded: dict[str, int] = {}
    unknown_af = 0
    kept: list[dict[str, Any]] = []

    def drop(reason: str) -> None:
        excluded[reason] = excluded.get(reason, 0) + 1

    for rec in _records(path, fmt, params):
        funnel["examined"] += 1

        cons_ok = _passes_consequence(rec, params)
        if cons_ok is False:
            drop("consequence")
            continue
        funnel["after_consequence"] += 1

        af_val: float | None = None
        if af_field:
            af_val = _max_float(get_field(rec, af_field))
            if af_val is None:
                unknown_af += 1
                if not keep_unknown_af:
                    drop("unknown_frequency")
                    continue
            elif af_max is not None and af_val > af_max:
                drop("frequency")
                continue
        funnel["after_frequency"] += 1

        if gene_allowlist:
            gene = (get_field(rec, gene_field) or "").strip() if gene_field else ""
            if gene not in gene_allowlist:
                drop("gene_not_in_panel")
                continue
        funnel["after_gene"] += 1

        if qual_field and qual_min is not None:
            q = _max_float(get_field(rec, qual_field))
            if q is not None and q < qual_min:
                drop("low_quality")
                continue
        if depth_field and depth_min is not None:
            d = _max_float(get_field(rec, depth_field))
            if d is not None and d < depth_min:
                drop("low_depth")
                continue
        funnel["after_quality"] += 1

        if zygosity:
            gt = rec.get("gt") or (get_field(rec, params.get("zygosity_field", "")) or "")
            alleles = re.split(r"[/|]", str(gt)) if gt else []
            is_hom = bool(alleles) and len(set(a for a in alleles if a not in ("", "."))) == 1 and "0" not in alleles
            if zygosity == "hom" and not is_hom:
                drop("zygosity")
                continue
            if zygosity == "het" and is_hom:
                drop("zygosity")
                continue
        funnel["after_zygosity"] += 1

        candidate = {
            "chrom": rec.get("chrom") or get_field(rec, params.get("chrom_field", "")),
            "pos": rec.get("pos") or get_field(rec, params.get("pos_field", "")),
            "ref": rec.get("ref") or get_field(rec, params.get("ref_field", "")),
            "alt": rec.get("alt") or get_field(rec, params.get("alt_field", "")),
            "gene": (get_field(rec, gene_field) if gene_field else None),
            "consequence": (get_field(rec, params.get("consequence_field", "")) or None),
            "population_frequency_supplied": af_val,
            "genome_build": build,
        }
        if rec.get("gt"):
            candidate["genotype_supplied"] = rec.get("gt")
        kept.append(candidate)
        if len(kept) >= limit:
            excluded["truncated_at_limit"] = excluded.get("truncated_at_limit", 0) + 1

    # Rank kept candidates: rarer first, then more-severe consequence.
    def sort_key(c: dict[str, Any]) -> tuple[float, int]:
        af = c["population_frequency_supplied"]
        af_key = af if isinstance(af, float) else -1.0  # unknown AF ranks with rarest
        terms = _consequence_terms(c.get("consequence"))
        sev = min((_SEVERITY_RANK.get(t, 10_000) for t in terms), default=10_000)
        return (af_key, sev)

    kept.sort(key=sort_key)
    shortlisted = kept[:limit]
    funnel["shortlisted"] = len(shortlisted)

    return {
        "version": VERSION,
        "artifact": "variant_prioritization",
        "file_sha256": file_sha256(path),
        "format": fmt,
        "genome_build": build,
        "parameters": params,
        "funnel": funnel,
        "unknown_frequency_kept": unknown_af if keep_unknown_af else 0,
        "excluded_class_counts": dict(sorted(excluded.items())),
        "candidates": shortlisted,
        "candidate_count": len(shortlisted),
        "notes": [
            "Filtering removes nothing from the source; excluded classes are counted, not deleted.",
            "Zygosity and genotype are candidate signals only; no phasing, segregation, or de-novo status is inferred.",
            "Every annotation is copied from the file as supplied and is not independently verified.",
        ],
    }


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", action="version", version=VERSION)
    sub = parser.add_subparsers(dest="command", required=True)

    p_ins = sub.add_parser("inspect", help="report format and candidate annotation fields")
    p_ins.add_argument("input")
    p_ins.add_argument("--format", choices=["vcf", "tsv", "csv", "xlsx"])
    p_ins.add_argument("--sheet-index", type=int, default=0, dest="sheet_index")
    p_ins.add_argument("--header-row", type=int, default=0, dest="header_row")
    p_ins.add_argument("--output")
    p_ins.set_defaults(func=cmd_inspect)

    p_flt = sub.add_parser("filter", help="apply reviewer-approved deterministic filters")
    p_flt.add_argument("input")
    p_flt.add_argument("--params", required=True, help="JSON file of filter parameters")
    p_flt.add_argument("--output")
    p_flt.set_defaults(func=cmd_filter)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = args.func(args)
    except ReviewError as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2
    payload = json.dumps(result, indent=2, ensure_ascii=False)
    if getattr(args, "output", None):
        Path(args.output).write_text(payload + "\n", encoding="utf-8")
        print(f"wrote {args.output}")
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
