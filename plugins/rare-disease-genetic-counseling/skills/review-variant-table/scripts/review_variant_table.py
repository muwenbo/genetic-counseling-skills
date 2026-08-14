#!/usr/bin/env python3
"""Inspect and extract scientific fields from variant tables without dependencies.

The script is deliberately non-interpretive. It inventories XLSX/CSV/TSV files,
proposes header candidates, and extracts only reviewer-mapped scientific columns.
It never executes macros or formulas and never prints cell values to stdout.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import posixpath
import re
import sys
import zipfile
from pathlib import Path
from typing import Any, Iterable, Iterator
from xml.etree import ElementTree as ET


VERSION = "0.1.0"
MAX_FILE_BYTES = 100 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 500 * 1024 * 1024
MAX_COMPRESSION_RATIO = 200
MAX_CELL_TEXT = 10_000

SHEET_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
DOC_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"

CANONICAL_FIELDS = {
    "gene",
    "chrom",
    "pos",
    "start",
    "end",
    "ref",
    "alt",
    "genomic_hgvs",
    "coding_hgvs",
    "protein_hgvs",
    "rsid",
    "transcript",
    "zygosity",
    "genotype",
    "sample_role",
    "genome_build",
    "cnv_type",
    "depth",
    "allele_depth",
    "allele_fraction",
    "quality",
    "filter",
    "consequence",
    "inheritance_supplied",
    "classification_supplied",
    "acmg_codes_supplied",
    "population_frequency_supplied",
    "clinvar_supplied",
}

HEADER_ALIASES = {
    "gene": {"gene", "genesymbol", "generefgene", "基因", "基因名称"},
    "chrom": {"chrom", "chromosome", "chr", "染色体"},
    "pos": {"pos", "position", "位置", "变异位置"},
    "start": {"start", "startposition", "起始", "起始位置"},
    "end": {"end", "endposition", "终止", "终止位置"},
    "ref": {"ref", "reference", "referenceallele", "参考", "参考等位基因"},
    "alt": {"alt", "alternate", "alternateallele", "替代", "替代等位基因"},
    "transcript": {"transcript", "transcriptid", "转录本", "转录本编号"},
    "coding_hgvs": {"chgvs", "hgvsc", "codinghgvs", "核苷酸改变"},
    "protein_hgvs": {"phgvs", "hgvsp", "proteinhgvs", "氨基酸改变"},
    "genomic_hgvs": {"ghgvs", "hgvsg", "genomichgvs", "基因组hgvs"},
    "rsid": {"rsid", "dbsnp", "snpid"},
    "zygosity": {"zygosity", "合子状态", "杂合状态"},
    "genotype": {"genotype", "gt", "基因型"},
    "genome_build": {"genomebuild", "assembly", "referencegenome", "参考基因组"},
    "cnv_type": {"cnvtype", "copynumbertype", "拷贝数类型"},
    "depth": {"depth", "dp", "测序深度", "覆盖深度"},
    "allele_depth": {"alleledepth", "ad", "等位基因深度"},
    "allele_fraction": {"allelefraction", "vaf", "af", "等位基因比例"},
    "quality": {"quality", "qual", "质量值"},
    "filter": {"filter", "过滤", "筛选结果"},
    "consequence": {"consequence", "effect", "function", "变异后果", "功能"},
    "classification_supplied": {
        "classification",
        "pathogenicity",
        "致病性",
        "临床意义",
    },
    "acmg_codes_supplied": {"acmg", "acmgcodes", "acmgcriteria", "acmg证据"},
    "population_frequency_supplied": {
        "populationfrequency",
        "gnomadaf",
        "maxaf",
        "人群频率",
    },
    "clinvar_supplied": {"clinvar", "clinvarsignificance", "clinvar临床意义"},
    "inheritance_supplied": {"inheritance", "moi", "遗传方式"},
}

IDENTIFIER_ALIASES = {
    "name",
    "patient",
    "patientname",
    "subject",
    "subjectid",
    "sample",
    "sampleid",
    "barcode",
    "accession",
    "medicalrecordnumber",
    "mrn",
    "姓名",
    "患者",
    "患者姓名",
    "样本",
    "样本编号",
    "条码",
    "检测编号",
    "住院号",
    "病历号",
}

NONIDENTIFYING_ROLES = {
    "proband",
    "patient",
    "mother",
    "father",
    "sibling",
    "brother",
    "sister",
    "parent",
    "母亲",
    "父亲",
    "先证者",
    "兄弟",
    "姐妹",
}


class TableError(Exception):
    """A safe, user-actionable table processing error."""


def qname(namespace: str, local: str) -> str:
    return f"{{{namespace}}}{local}"


def normalize_header(value: Any) -> str:
    text = "" if value is None else str(value)
    return re.sub(r"[^0-9a-zA-Z\u3400-\u9fff]+", "", text).lower()


def truncate_cell(value: Any) -> str:
    text = "" if value is None else str(value)
    return text[:MAX_CELL_TEXT]


def file_metadata(path: Path, file_format: str) -> dict[str, Any]:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return {
        "sha256": digest.hexdigest(),
        "format": file_format,
        "size_bytes": path.stat().st_size,
    }


def detect_format(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".xlsx":
        return "xlsx"
    if suffix == ".csv":
        return "csv"
    if suffix == ".tsv":
        return "tsv"
    if suffix in {".xls", ".xlsm"}:
        raise TableError(
            "legacy or macro-enabled Excel input is unsupported; use a trusted local conversion"
        )
    raise TableError("supported input formats are .xlsx, .csv, and .tsv")


def validate_input(path: Path) -> str:
    if not path.is_file():
        raise TableError("input file does not exist or is not a regular file")
    if path.stat().st_size > MAX_FILE_BYTES:
        raise TableError("input exceeds the 100 MiB safety limit")
    return detect_format(path)


def validate_xlsx_container(path: Path) -> None:
    try:
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            total = sum(item.file_size for item in infos)
            if total > MAX_UNCOMPRESSED_BYTES:
                raise TableError("workbook exceeds the uncompressed-size safety limit")
            for item in infos:
                if item.flag_bits & 0x1:
                    raise TableError("encrypted workbooks are unsupported")
                if item.file_size <= 0:
                    continue
                ratio = item.file_size / max(item.compress_size, 1)
                if ratio > MAX_COMPRESSION_RATIO:
                    raise TableError("workbook has a suspicious compression ratio")
            required = {"xl/workbook.xml", "xl/_rels/workbook.xml.rels"}
            if not required.issubset(set(archive.namelist())):
                raise TableError("file is not a readable XLSX workbook")
    except zipfile.BadZipFile as exc:
        raise TableError("file is not a readable XLSX workbook") from exc


def parse_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    try:
        root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    except ET.ParseError as exc:
        raise TableError("workbook shared strings are malformed") from exc
    values: list[str] = []
    for item in root.findall(qname(SHEET_NS, "si")):
        values.append("".join(node.text or "" for node in item.iter(qname(SHEET_NS, "t"))))
    return values


def workbook_sheets(archive: zipfile.ZipFile) -> list[dict[str, str]]:
    try:
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    except (KeyError, ET.ParseError) as exc:
        raise TableError("workbook metadata are malformed") from exc

    targets = {
        rel.get("Id"): rel.get("Target")
        for rel in rels.findall(qname(PKG_REL_NS, "Relationship"))
    }
    sheets: list[dict[str, str]] = []
    for sheet in workbook.findall(f".//{qname(SHEET_NS, 'sheet')}"):
        rel_id = sheet.get(qname(DOC_REL_NS, "id"))
        target = targets.get(rel_id)
        if not target:
            raise TableError("a workbook sheet relationship is missing")
        if target.startswith("/"):
            normalized = posixpath.normpath(target.lstrip("/"))
        else:
            normalized = posixpath.normpath(posixpath.join("xl", target))
        if not normalized.startswith("xl/") or normalized not in archive.namelist():
            raise TableError("a workbook sheet target is invalid")
        sheets.append(
            {
                "name": sheet.get("name") or "",
                "state": sheet.get("state") or "visible",
                "path": normalized,
            }
        )
    if not sheets:
        raise TableError("workbook contains no readable worksheets")
    return sheets


def column_index(reference: str) -> int:
    match = re.match(r"^([A-Za-z]+)", reference)
    if not match:
        raise TableError("a worksheet cell reference is malformed")
    result = 0
    for char in match.group(1).upper():
        result = result * 26 + ord(char) - ord("A") + 1
    return result


def column_label(index: int) -> str:
    if index < 1:
        raise ValueError("column indexes are 1-based")
    value = index
    letters = ""
    while value:
        value, remainder = divmod(value - 1, 26)
        letters = chr(ord("A") + remainder) + letters
    return letters


def parse_cell(cell: ET.Element, shared_strings: list[str]) -> dict[str, Any]:
    reference = cell.get("r") or ""
    index = column_index(reference)
    cell_type = cell.get("t")
    formula_node = cell.find(qname(SHEET_NS, "f"))
    value_node = cell.find(qname(SHEET_NS, "v"))
    formula = formula_node.text if formula_node is not None else None

    if cell_type == "inlineStr":
        value = "".join(node.text or "" for node in cell.iter(qname(SHEET_NS, "t")))
    elif cell_type == "s":
        try:
            if value_node is None or value_node.text is None:
                raise ValueError("missing shared-string index")
            shared_index = int(value_node.text)
            if shared_index < 0:
                raise IndexError("negative shared-string index")
            value = shared_strings[shared_index]
        except (ValueError, IndexError) as exc:
            raise TableError("a workbook shared-string reference is invalid") from exc
    elif cell_type == "b":
        value = value_node is not None and value_node.text == "1"
    elif cell_type == "e":
        value = value_node.text if value_node is not None else "#ERROR"
    else:
        value = value_node.text if value_node is not None else None

    return {
        "column": index,
        "value": truncate_cell(value) if isinstance(value, str) else value,
        "formula": truncate_cell(formula) if formula is not None else None,
    }


def iter_xlsx_rows(
    archive: zipfile.ZipFile, sheet_path: str, shared_strings: list[str]
) -> Iterator[tuple[int, dict[int, dict[str, Any]]]]:
    try:
        handle = archive.open(sheet_path)
    except KeyError as exc:
        raise TableError("selected worksheet is unavailable") from exc
    with handle:
        try:
            for _event, element in ET.iterparse(handle, events=("end",)):
                if element.tag != qname(SHEET_NS, "row"):
                    continue
                row_number = int(element.get("r") or 0)
                cells: dict[int, dict[str, Any]] = {}
                for cell in element.findall(qname(SHEET_NS, "c")):
                    parsed = parse_cell(cell, shared_strings)
                    cells[parsed["column"]] = parsed
                yield row_number, cells
                element.clear()
        except (ET.ParseError, ValueError) as exc:
            raise TableError("selected worksheet XML is malformed") from exc


def matched_header_fields(values: Iterable[Any]) -> set[str]:
    matches: set[str] = set()
    for value in values:
        normalized = normalize_header(value)
        if not normalized:
            continue
        for field, aliases in HEADER_ALIASES.items():
            normalized_aliases = {normalize_header(alias) for alias in aliases}
            if normalized in normalized_aliases:
                matches.add(field)
                continue
            if any(
                alias and len(alias) >= 4 and alias in normalized
                for alias in normalized_aliases
            ):
                matches.add(field)
    return matches


def possible_identifier_columns(cells: dict[int, dict[str, Any]]) -> list[dict[str, Any]]:
    aliases = {normalize_header(alias) for alias in IDENTIFIER_ALIASES}
    result = []
    for index, cell in sorted(cells.items()):
        normalized = normalize_header(cell.get("value"))
        if normalized in aliases or any(
            alias and len(alias) >= 4 and alias in normalized for alias in aliases
        ):
            result.append(
                {"column": column_label(index), "header": truncate_cell(cell.get("value"))}
            )
    return result


def header_candidate(row_number: int, cells: dict[int, dict[str, Any]]) -> dict[str, Any] | None:
    matches = matched_header_fields(cell.get("value") for cell in cells.values())
    core = matches.intersection({"chrom", "pos", "start", "ref", "alt", "genomic_hgvs"})
    score = len(matches) + len(core)
    if score < 2:
        return None
    headers = [
        {"column": column_label(index), "value": truncate_cell(cell.get("value"))}
        for index, cell in sorted(cells.items())
        if cell.get("value") not in (None, "")
    ]
    return {
        "row": row_number,
        "score": score,
        "matched_fields": sorted(matches),
        "headers": headers,
        "possible_identifier_columns": possible_identifier_columns(cells),
    }


def inspect_xlsx(path: Path, scan_rows: int) -> dict[str, Any]:
    validate_xlsx_container(path)
    sheet_results = []
    warnings: list[str] = []
    with zipfile.ZipFile(path) as archive:
        names = {name.lower() for name in archive.namelist()}
        if any(name.endswith("vbaproject.bin") for name in names):
            warnings.append("vba_content_present")
        if any(name.startswith("xl/externallinks/") for name in names):
            warnings.append("external_links_present")
        shared_strings = parse_shared_strings(archive)
        for sheet_index, sheet in enumerate(workbook_sheets(archive), start=1):
            row_count = 0
            max_column = 0
            formula_count = 0
            candidates = []
            merged_count = 0
            with archive.open(sheet["path"]) as handle:
                try:
                    for _event, element in ET.iterparse(handle, events=("end",)):
                        if element.tag == qname(SHEET_NS, "row"):
                            row_number = int(element.get("r") or 0)
                            cells: dict[int, dict[str, Any]] = {}
                            for cell in element.findall(qname(SHEET_NS, "c")):
                                parsed = parse_cell(cell, shared_strings)
                                cells[parsed["column"]] = parsed
                                if parsed["formula"] is not None:
                                    formula_count += 1
                            row_count = max(row_count, row_number)
                            max_column = max(max_column, max(cells, default=0))
                            if row_number <= scan_rows:
                                candidate = header_candidate(row_number, cells)
                                if candidate is not None:
                                    candidates.append(candidate)
                            element.clear()
                        elif element.tag == qname(SHEET_NS, "mergeCell"):
                            merged_count += 1
                except (ET.ParseError, ValueError) as exc:
                    raise TableError("a worksheet is malformed") from exc
            candidates.sort(key=lambda item: (-item["score"], item["row"]))
            sheet_results.append(
                {
                    "ref": f"sheet_{sheet_index}",
                    "state": sheet["state"],
                    "row_count": row_count,
                    "column_count": max_column,
                    "formula_count": formula_count,
                    "merged_range_count": merged_count,
                    "header_candidates": candidates[:5],
                }
            )
            if formula_count:
                warnings.append("formula_cells_present")
            if sheet["state"] != "visible":
                warnings.append("hidden_sheets_present")
    return {
        "schema_version": VERSION,
        "operation": "inspect",
        "source_file": file_metadata(path, "xlsx"),
        "workbook": {"sheets": sheet_results, "warnings": sorted(set(warnings))},
        "selection": None,
        "review_required": True,
    }


def csv_dialect(path: Path, file_format: str) -> csv.Dialect:
    if file_format == "tsv":
        class TsvDialect(csv.excel):
            delimiter = "\t"

        return TsvDialect()
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            sample = handle.read(65536)
    except UnicodeDecodeError as exc:
        raise TableError("delimited input must be UTF-8 encoded") from exc
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        return csv.excel()


def iter_delimited_rows(path: Path, file_format: str) -> Iterator[tuple[int, dict[int, dict[str, Any]]]]:
    dialect = csv_dialect(path, file_format)
    try:
        handle = path.open("r", encoding="utf-8-sig", newline="")
    except UnicodeDecodeError as exc:
        raise TableError("delimited input must be UTF-8 encoded") from exc
    with handle:
        try:
            reader = csv.reader(handle, dialect)
            for row_number, row in enumerate(reader, start=1):
                yield row_number, {
                    index: {"column": index, "value": truncate_cell(value), "formula": None}
                    for index, value in enumerate(row, start=1)
                }
        except (csv.Error, UnicodeDecodeError) as exc:
            raise TableError("delimited input is malformed or not UTF-8") from exc


def inspect_delimited(path: Path, file_format: str, scan_rows: int) -> dict[str, Any]:
    row_count = 0
    max_column = 0
    candidates = []
    for row_number, cells in iter_delimited_rows(path, file_format):
        row_count = row_number
        max_column = max(max_column, max(cells, default=0))
        if row_number <= scan_rows:
            candidate = header_candidate(row_number, cells)
            if candidate is not None:
                candidates.append(candidate)
    candidates.sort(key=lambda item: (-item["score"], item["row"]))
    return {
        "schema_version": VERSION,
        "operation": "inspect",
        "source_file": file_metadata(path, file_format),
        "workbook": {
            "sheets": [
                {
                    "ref": "table",
                    "state": "visible",
                    "row_count": row_count,
                    "column_count": max_column,
                    "formula_count": 0,
                    "merged_range_count": 0,
                    "header_candidates": candidates[:5],
                }
            ],
            "warnings": [],
        },
        "selection": None,
        "review_required": True,
    }


def load_mapping(path: Path) -> dict[str, str]:
    try:
        with path.open(encoding="utf-8") as handle:
            mapping = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise TableError("mapping file is missing or malformed JSON") from exc
    if not isinstance(mapping, dict) or not mapping:
        raise TableError("mapping must be a non-empty JSON object")
    unknown = sorted(set(mapping) - CANONICAL_FIELDS)
    if unknown:
        raise TableError("mapping contains unsupported canonical fields")
    if not all(isinstance(value, str) and value.strip() for value in mapping.values()):
        raise TableError("every mapping value must name a non-empty source column")
    return {key: value.strip() for key, value in mapping.items()}


def resolve_mapping(
    mapping: dict[str, str], header_cells: dict[int, dict[str, Any]]
) -> tuple[dict[str, int], list[dict[str, str]]]:
    by_header: dict[str, list[int]] = {}
    for index, cell in header_cells.items():
        text = "" if cell.get("value") is None else str(cell.get("value"))
        by_header.setdefault(text, []).append(index)

    resolved: dict[str, int] = {}
    audit = []
    for canonical, source in mapping.items():
        exact = by_header.get(source, [])
        if len(exact) == 1:
            index = exact[0]
        elif len(exact) > 1:
            raise TableError("a mapped header is duplicated; use its spreadsheet column label")
        elif re.fullmatch(r"[A-Za-z]{1,3}", source):
            index = column_index(source)
            if index not in header_cells:
                raise TableError("a mapped spreadsheet column has no header cell")
        else:
            raise TableError("a mapped source column was not found in the reviewed header")
        if index in resolved.values():
            raise TableError("one source column cannot map to multiple canonical fields")
        resolved[canonical] = index
        audit.append(
            {
                "canonical_field": canonical,
                "source_column": column_label(index),
                "source_header": truncate_cell(header_cells[index].get("value")),
                "status": "accepted",
            }
        )
    return resolved, audit


def normalized_build(value: Any) -> str | None:
    normalized = normalize_header(value)
    if normalized in {"hg19", "grch37"}:
        return "hg19"
    if normalized in {"hg38", "grch38"}:
        return "hg38"
    return None


def row_issues(fields: dict[str, Any], genome_build: str | None, coordinate: str | None) -> list[str]:
    issues: list[str] = []
    has_genomic = all(fields.get(field) not in (None, "") for field in ("chrom", "pos", "ref", "alt"))
    has_cnv = all(fields.get(field) not in (None, "") for field in ("chrom", "start", "end", "cnv_type"))
    has_named = any(fields.get(field) not in (None, "") for field in ("genomic_hgvs", "coding_hgvs", "rsid"))
    if not (has_genomic or has_cnv or has_named):
        issues.append("variant_representation_incomplete")
    if fields.get("coding_hgvs") not in (None, "") and fields.get("transcript") in (None, ""):
        issues.append("transcript_missing_for_coding_hgvs")
    if has_genomic or has_cnv:
        row_build = normalized_build(fields.get("genome_build"))
        if fields.get("genome_build") not in (None, "") and row_build is None:
            issues.append("genome_build_unrecognized")
        if genome_build is None and row_build is None:
            issues.append("genome_build_missing")
        if genome_build is not None and row_build is not None and genome_build != row_build:
            issues.append("genome_build_conflict")
        if coordinate is None:
            issues.append("coordinate_convention_missing")
    return issues


def extract_records(
    rows: Iterable[tuple[int, dict[int, dict[str, Any]]]],
    sheet_ref: str,
    header_row: int,
    data_start_row: int,
    data_end_row: int | None,
    mapping: dict[str, str],
    genome_build: str | None,
    coordinate: str | None,
) -> tuple[list[dict[str, Any]], dict[str, int], list[dict[str, str]]]:
    header_cells: dict[int, dict[str, Any]] | None = None
    resolved: dict[str, int] | None = None
    audit: list[dict[str, str]] = []
    records: list[dict[str, Any]] = []
    reconciliation = {
        "examined": 0,
        "accepted": 0,
        "unresolved": 0,
        "rejected": 0,
        "blank": 0,
    }
    previous_row = data_start_row - 1

    for row_number, cells in rows:
        if row_number == header_row:
            header_cells = cells
            resolved, audit = resolve_mapping(mapping, cells)
            continue
        if row_number < data_start_row:
            continue
        if data_end_row is not None and row_number > data_end_row:
            break
        if resolved is None:
            raise TableError("the reviewed header row was not found before the data range")

        if row_number > previous_row + 1:
            missing = row_number - previous_row - 1
            reconciliation["examined"] += missing
            reconciliation["blank"] += missing
        previous_row = row_number
        reconciliation["examined"] += 1

        raw_nonblank = any(cell.get("value") not in (None, "") for cell in cells.values())
        fields = {
            canonical: cells.get(index, {}).get("value")
            for canonical, index in resolved.items()
        }
        mapped_nonblank = any(value not in (None, "") for value in fields.values())
        if not raw_nonblank:
            reconciliation["blank"] += 1
            continue

        issues = []
        if not mapped_nonblank:
            issues.append("no_mapped_scientific_values")
        if any(cells.get(index, {}).get("formula") is not None for index in resolved.values()):
            issues.append("formula_cell_present")
        if "sample_role" in fields and fields["sample_role"] not in (None, ""):
            role = normalize_header(fields["sample_role"])
            allowed_roles = {normalize_header(value) for value in NONIDENTIFYING_ROLES}
            if role not in allowed_roles:
                fields["sample_role"] = None
                issues.append("sample_role_not_nonidentifying")
        issues.extend(row_issues(fields, genome_build, coordinate))
        disposition = "unresolved" if issues else "accepted"
        if disposition == "unresolved":
            reconciliation["unresolved"] += 1
        else:
            reconciliation["accepted"] += 1
        records.append(
            {
                "source_sheet": sheet_ref,
                "source_row": row_number,
                "disposition": disposition,
                "fields": fields,
                "issues": sorted(set(issues)),
            }
        )

    if header_cells is None:
        raise TableError("the reviewed header row was not found")
    if data_end_row is not None and previous_row < data_end_row:
        missing = data_end_row - max(previous_row, data_start_row - 1)
        reconciliation["examined"] += missing
        reconciliation["blank"] += missing
    return records, reconciliation, audit


def extract_table(args: argparse.Namespace, path: Path, file_format: str) -> dict[str, Any]:
    if args.data_start_row <= args.header_row:
        raise TableError("data-start-row must be greater than header-row")
    if args.data_end_row is not None and args.data_end_row < args.data_start_row:
        raise TableError("data-end-row must not precede data-start-row")
    mapping = load_mapping(args.mapping)

    if file_format == "xlsx":
        validate_xlsx_container(path)
        with zipfile.ZipFile(path) as archive:
            shared_strings = parse_shared_strings(archive)
            sheets = workbook_sheets(archive)
            if args.sheet_index < 1 or args.sheet_index > len(sheets):
                raise TableError("the reviewed sheet index is out of range")
            selected = sheets[args.sheet_index - 1]
            sheet_ref = f"sheet_{args.sheet_index}"
            records, reconciliation, audit = extract_records(
                iter_xlsx_rows(archive, selected["path"], shared_strings),
                sheet_ref,
                args.header_row,
                args.data_start_row,
                args.data_end_row,
                mapping,
                args.genome_build,
                args.coordinate_convention,
            )
    else:
        if args.sheet_index != 1:
            raise TableError("CSV and TSV inputs use sheet index 1")
        sheet_ref = "table"
        records, reconciliation, audit = extract_records(
            iter_delimited_rows(path, file_format),
            "table",
            args.header_row,
            args.data_start_row,
            args.data_end_row,
            mapping,
            args.genome_build,
            args.coordinate_convention,
        )

    blocking_codes = sorted(
        {
            issue
            for record in records
            for issue in record["issues"]
            if issue
            in {
                "genome_build_missing",
                "genome_build_unrecognized",
                "genome_build_conflict",
                "coordinate_convention_missing",
                "sample_role_not_nonidentifying",
            }
        }
    )
    if args.sample_scope is None:
        blocking_codes.append("sample_scope_missing")
    blocking_codes = sorted(set(blocking_codes))
    return {
        "schema_version": VERSION,
        "operation": "extract",
        "status": "incomplete"
        if blocking_codes or reconciliation["unresolved"]
        else "ready_for_review",
        "source_file": file_metadata(path, file_format),
        "selection": {
            "sheet_ref": sheet_ref,
            "header_row": args.header_row,
            "data_start_row": args.data_start_row,
            "data_end_row": args.data_end_row,
            "reviewer_status": "accepted",
        },
        "context": {
            "assay_type": args.assay_type,
            "sample_scope": args.sample_scope,
            "genome_build": args.genome_build,
            "coordinate_convention": args.coordinate_convention,
        },
        "column_mappings": audit,
        "row_reconciliation": reconciliation,
        "records": records,
        "blocking_issues": blocking_codes,
        "review_required": True,
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        raise TableError("output file already exists; choose a new path")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inspect and extract reviewable scientific fields from variant tables."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser("inspect", help="inventory a table without selecting data")
    inspect_parser.add_argument("input", type=Path)
    inspect_parser.add_argument("--output", type=Path, required=True)
    inspect_parser.add_argument("--scan-rows", type=int, default=100)

    extract_parser = subparsers.add_parser("extract", help="extract an approved scientific mapping")
    extract_parser.add_argument("input", type=Path)
    extract_parser.add_argument("--output", type=Path, required=True)
    extract_parser.add_argument("--sheet-index", type=int, required=True)
    extract_parser.add_argument("--header-row", type=int, required=True)
    extract_parser.add_argument("--data-start-row", type=int, required=True)
    extract_parser.add_argument("--data-end-row", type=int)
    extract_parser.add_argument("--mapping", type=Path, required=True)
    extract_parser.add_argument("--genome-build", choices=("hg19", "hg38"))
    extract_parser.add_argument("--coordinate-convention")
    extract_parser.add_argument(
        "--sample-scope",
        choices=("proband_only", "trio", "family", "mixed", "unknown"),
    )
    extract_parser.add_argument(
        "--assay-type",
        choices=("wes", "wgs", "panel", "targeted", "unknown"),
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        file_format = validate_input(args.input)
        if args.output.resolve() == args.input.resolve():
            raise TableError("output must not overwrite the source file")
        if args.command == "inspect":
            if args.scan_rows < 1 or args.scan_rows > 1000:
                raise TableError("scan-rows must be between 1 and 1000")
            if file_format == "xlsx":
                payload = inspect_xlsx(args.input, args.scan_rows)
            else:
                payload = inspect_delimited(args.input, file_format, args.scan_rows)
        else:
            payload = extract_table(args, args.input, file_format)
        write_json(args.output, payload)
        summary = {
            "operation": payload["operation"],
            "source_sha256": payload["source_file"]["sha256"],
            "output_written": True,
        }
        if payload["operation"] == "inspect":
            summary["sheet_count"] = len(payload["workbook"]["sheets"])
        else:
            summary["row_reconciliation"] = payload["row_reconciliation"]
            summary["blocking_issues"] = payload["blocking_issues"]
        print(json.dumps(summary, ensure_ascii=False))
        return 0
    except TableError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
