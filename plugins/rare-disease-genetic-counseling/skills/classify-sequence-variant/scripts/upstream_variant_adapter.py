#!/usr/bin/env python3
"""Safety adapter for the pinned upstream variant-classifier resources."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence


UPSTREAM_REPOSITORY = "https://github.com/muwenbo/vcep-classification-skills"
EXPECTED_COMMIT = "05bf1f6bce4e6be04f9e52b55db1d5fee03029d9"
UPSTREAM_SKILL_RELATIVE = Path("plugins/variant-classifier/skills/variant-classifier")
DEFAULT_VENDOR_RELATIVE = Path("vendor/vcep-classification-skills")
ENSEMBL_REST_URL = "https://rest.ensembl.org"
ENSEMBL_GRCH37_REST_URL = "https://grch37.rest.ensembl.org"
NCBI_VARIATION_URL = "https://api.ncbi.nlm.nih.gov/variation/v0"
GENOMIC_PATTERNS = (
    re.compile(
        r"^(?:chr)?(?P<chrom>[A-Za-z0-9]+)[:-](?P<pos>[0-9]+)[:-]"
        r"(?P<ref>[ACGTN]+)[:-](?P<alt>[ACGTN]+)$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:chr)?(?P<chrom>[A-Za-z0-9]+)[:-](?P<pos>[0-9]+)[:-]"
        r"(?P<ref>[ACGTN]+)>(?P<alt>[ACGTN]+)$",
        re.IGNORECASE,
    ),
)
GENE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,31}$")
TRANSCRIPT_HGVS_PATTERN = re.compile(r"^N[MR]_[0-9]+\.[0-9]+:[cn]\..+$")
GENOMIC_HGVS_PATTERN = re.compile(r"^NC_[0-9]+\.[0-9]+:g\..+$")
BUILD_TO_ASSEMBLY = {"hg19": "GRCh37", "hg38": "GRCh38"}
BUILD_TO_ENSEMBL_URL = {
    "hg19": ENSEMBL_GRCH37_REST_URL,
    "hg38": ENSEMBL_REST_URL,
}


@dataclass(frozen=True)
class Dependency:
    root: Path
    skill_root: Path
    commit: str


class AdapterError(RuntimeError):
    """Expected adapter failure with a stable machine-readable reason."""

    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def dependency_candidates(explicit: str | None) -> list[Path]:
    if explicit:
        return [Path(explicit).expanduser()]
    environment_root = os.environ.get("RARE_DISEASE_VCEP_ROOT")
    if environment_root:
        return [Path(environment_root).expanduser()]

    candidates: list[Path] = []
    for origin in (Path.cwd(), Path(__file__).resolve()):
        start = origin if origin.is_dir() else origin.parent
        for parent in (start, *start.parents):
            candidates.append(parent / DEFAULT_VENDOR_RELATIVE)

    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate.resolve(strict=False))
        if key not in seen:
            seen.add(key)
            unique.append(candidate)
    return unique


def normalize_dependency_root(candidate: Path) -> tuple[Path, Path] | None:
    candidate = candidate.resolve(strict=False)
    nested_skill = candidate / UPSTREAM_SKILL_RELATIVE
    if nested_skill.is_dir():
        return candidate, nested_skill
    if (
        candidate.name == "variant-classifier"
        and (candidate / "scripts/vep_annotate.py").is_file()
        and (candidate / "data/vcep_registry.json").is_file()
    ):
        repository_root = candidate
        for _ in UPSTREAM_SKILL_RELATIVE.parts:
            repository_root = repository_root.parent
        return repository_root, candidate
    return None


def git_commit(repository_root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(repository_root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise AdapterError(
            "upstream_commit_unverifiable",
            "The upstream directory is present, but its Git commit cannot be verified.",
        ) from exc
    return result.stdout.strip()


def resolve_dependency(explicit: str | None = None) -> Dependency:
    mismatch_seen = False
    for candidate in dependency_candidates(explicit):
        normalized = normalize_dependency_root(candidate)
        if not normalized:
            continue
        repository_root, skill_root = normalized
        commit = git_commit(repository_root)
        if commit != EXPECTED_COMMIT:
            mismatch_seen = True
            continue
        required = (
            skill_root / "scripts/vep_annotate.py",
            skill_root / "scripts/check_vcep_spec.py",
            skill_root / "data/vcep_registry.json",
        )
        if not all(path.is_file() for path in required):
            raise AdapterError(
                "upstream_layout_invalid",
                "The pinned upstream checkout is missing required variant-classifier resources.",
            )
        return Dependency(repository_root, skill_root, commit)

    if mismatch_seen:
        raise AdapterError(
            "upstream_commit_mismatch",
            f"The upstream checkout is not pinned to required commit {EXPECTED_COMMIT}.",
        )
    raise AdapterError(
        "upstream_dependency_unavailable",
        "The pinned vcep-classification-skills checkout is unavailable.",
    )


def provenance(operation: str) -> dict[str, Any]:
    return {
        "repository": UPSTREAM_REPOSITORY,
        "commit": EXPECTED_COMMIT,
        "operation": operation,
        "retrieved_at": utc_now(),
    }


def upstream_license_status(root: Path) -> str:
    """Report the vendored upstream's standalone license file state."""
    license_file = root / "LICENSE"
    if not license_file.is_file():
        return "release_blocked_pending_standalone_license_file"
    first_line = (
        license_file.read_text(encoding="utf-8", errors="replace").strip().splitlines()
    )
    if first_line and "MIT License" in first_line[0]:
        return "mit_license_present"
    return "review_required_unrecognized_license"


def status_payload(explicit: str | None = None) -> tuple[dict[str, Any], int]:
    try:
        dependency = resolve_dependency(explicit)
    except AdapterError as exc:
        return (
            {
                "status": "capability_unavailable",
                "reason": exc.reason,
                "message": str(exc),
                "repository": UPSTREAM_REPOSITORY,
                "required_commit": EXPECTED_COMMIT,
                "supported_operations": [],
                "classification_engine_enabled": False,
                "license_status": "pinned_mit_license_expected_dependency_unavailable",
            },
            3,
        )

    guideline_count = len(
        list((dependency.skill_root / "data/vcep-guidelines").glob("*.md"))
    )
    return (
        {
            "status": "ok",
            "repository": UPSTREAM_REPOSITORY,
            "commit": dependency.commit,
            "supported_operations": ["annotate", "liftover", "vcep_lookup"],
            "annotation_assemblies": ["GRCh38", "GRCh37"],
            "annotation_endpoints": [ENSEMBL_REST_URL, ENSEMBL_GRCH37_REST_URL],
            "classification_engine_enabled": False,
            "classification_engine_reason": (
                "The upstream classifier conflicts with local PVS1, PM2, and "
                "four-state evidence guardrails."
            ),
            "vcep_guideline_count": guideline_count,
            "license_status": upstream_license_status(dependency.root),
        },
        0,
    )


def detect_genomic_variant(notation: str) -> dict[str, Any] | None:
    for pattern in GENOMIC_PATTERNS:
        match = pattern.fullmatch(notation.strip())
        if match:
            values = match.groupdict()
            return {
                "chrom": values["chrom"].removeprefix("chr"),
                "pos": int(values["pos"]),
                "ref": values["ref"].upper(),
                "alt": values["alt"].upper(),
            }
    return None


def is_supported_simple_allele(allele: dict[str, Any]) -> bool:
    """Return whether a parsed VCF-style allele is a supported SNV or simple indel."""
    chrom = str(allele["chrom"]).upper()
    ref = str(allele["ref"]).upper()
    alt = str(allele["alt"]).upper()
    if chrom in {"M", "MT"} or ref == alt or set(ref + alt) - set("ACGT"):
        return False
    if len(ref) == len(alt):
        return len(ref) == 1
    return ref[0] == alt[0] and (len(ref) == 1 or len(alt) == 1)


def ensembl_json(base_url: str, path: str, timeout_seconds: int) -> dict[str, Any]:
    request = urllib.request.Request(
        f"{base_url}/{path}",
        headers={
            "Accept": "application/json",
            "User-Agent": "rare-disease-genetic-counseling/0.1",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        if exc.code == 429:
            raise AdapterError(
                "remote_rate_limited", "Ensembl rate-limited the request."
            ) from exc
        raise AdapterError(
            "ensembl_service_failure", "Ensembl rejected the scientific request."
        ) from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise AdapterError(
            "ensembl_service_failure",
            "Ensembl could not complete the scientific request.",
        ) from exc
    if not isinstance(payload, dict):
        raise AdapterError(
            "ensembl_response_malformed", "Ensembl returned a malformed response."
        )
    return payload


def fetch_reference_sequence(
    build: str, chrom: str, start: int, end: int, timeout_seconds: int
) -> str:
    if start < 1 or end < start:
        raise AdapterError(
            "liftover_coordinates_invalid", "Reference interval is invalid."
        )
    region = urllib.parse.quote(f"{chrom}:{start}..{end}:1", safe=":.")
    payload = ensembl_json(
        BUILD_TO_ENSEMBL_URL[build],
        f"sequence/region/human/{region}?content-type=application/json",
        timeout_seconds,
    )
    sequence = payload.get("seq")
    if not isinstance(sequence, str) or len(sequence) != end - start + 1:
        raise AdapterError(
            "reference_sequence_unavailable",
            "Ensembl did not return the expected reference sequence length.",
        )
    return sequence.upper()


def reverse_complement(sequence: str) -> str:
    return sequence.translate(str.maketrans("ACGT", "TGCA"))[::-1]


def normalize_vcf_allele(
    build: str,
    chrom: str,
    pos: int,
    ref: str,
    alt: str,
    timeout_seconds: int,
) -> dict[str, Any]:
    """Minimize and left-align one simple VCF-style sequence allele."""
    ref, alt = ref.upper(), alt.upper()
    if not ref or not alt or set(ref + alt) - set("ACGT"):
        raise AdapterError(
            "liftover_allele_unsupported",
            "Liftover requires non-empty A/C/G/T REF and ALT.",
        )
    observed = fetch_reference_sequence(
        build, chrom, pos, pos + len(ref) - 1, timeout_seconds
    )
    if observed != ref:
        raise AdapterError(
            "source_ref_mismatch",
            f"Source REF does not match the declared {BUILD_TO_ASSEMBLY[build]} reference.",
        )

    while len(ref) > 1 and len(alt) > 1 and ref[-1] == alt[-1]:
        ref, alt = ref[:-1], alt[:-1]
    while len(ref) > 1 and len(alt) > 1 and ref[0] == alt[0]:
        ref, alt, pos = ref[1:], alt[1:], pos + 1

    if len(ref) != len(alt):
        while pos > 1 and ref[-1] == alt[-1]:
            previous = fetch_reference_sequence(
                build, chrom, pos - 1, pos - 1, timeout_seconds
            )
            ref, alt, pos = previous + ref[:-1], previous + alt[:-1], pos - 1
        while len(ref) > 1 and len(alt) > 1 and ref[-1] == alt[-1]:
            ref, alt = ref[:-1], alt[:-1]
        while len(ref) > 1 and len(alt) > 1 and ref[0] == alt[0]:
            ref, alt, pos = ref[1:], alt[1:], pos + 1

    final_ref = fetch_reference_sequence(
        build, chrom, pos, pos + len(ref) - 1, timeout_seconds
    )
    if final_ref != ref:
        raise AdapterError(
            "normalized_ref_mismatch",
            "Normalized REF does not match the reference assembly.",
        )
    return {"chrom": chrom, "pos": pos, "ref": ref, "alt": alt}


def map_assembly_region(
    from_build: str,
    to_build: str,
    chrom: str,
    start: int,
    end: int,
    timeout_seconds: int,
) -> dict[str, Any]:
    from_assembly = BUILD_TO_ASSEMBLY[from_build]
    to_assembly = BUILD_TO_ASSEMBLY[to_build]
    region = urllib.parse.quote(f"{chrom}:{start}..{end}:1", safe=":.")
    payload = ensembl_json(
        BUILD_TO_ENSEMBL_URL[from_build],
        f"map/human/{from_assembly}/{region}/{to_assembly}?content-type=application/json",
        timeout_seconds,
    )
    mappings = payload.get("mappings")
    if not isinstance(mappings, list) or len(mappings) != 1:
        raise AdapterError(
            "liftover_mapping_ambiguous",
            "Ensembl did not return exactly one contiguous assembly mapping.",
        )
    mapping = mappings[0]
    if not isinstance(mapping, dict) or not isinstance(mapping.get("mapped"), dict):
        raise AdapterError(
            "liftover_response_malformed", "Ensembl mapping fields are incomplete."
        )
    mapped = mapping["mapped"]
    required = ("assembly", "seq_region_name", "start", "end", "strand")
    if any(key not in mapped for key in required):
        raise AdapterError(
            "liftover_response_malformed", "Ensembl mapped region is incomplete."
        )
    if mapped["assembly"] != to_assembly or mapped["strand"] not in (-1, 1):
        raise AdapterError(
            "liftover_mapping_inconsistent",
            "Ensembl returned an unexpected assembly or strand.",
        )
    if abs(int(mapped["end"]) - int(mapped["start"])) + 1 != end - start + 1:
        raise AdapterError(
            "liftover_mapping_split",
            "The reference allele did not map as one length-preserving span.",
        )
    return mapping


def liftover_payload(
    variant: str,
    from_build: str,
    to_build: str,
    timeout_seconds: int = 30,
) -> tuple[dict[str, Any], int]:
    genomic = detect_genomic_variant(variant.strip())
    if not genomic:
        return error_payload(
            "blocked",
            "liftover_variant_invalid",
            "Use a simple genomic REF/ALT representation.",
        ), 2
    if not is_supported_simple_allele(genomic):
        return error_payload(
            "blocked",
            "liftover_allele_unsupported",
            "Liftover supports non-mitochondrial SNVs and simple anchored indels only.",
        ), 2
    if from_build == to_build:
        return error_payload(
            "blocked",
            "liftover_builds_identical",
            "Source and target genome builds must differ.",
        ), 2

    try:
        source = normalize_vcf_allele(
            from_build, **genomic, timeout_seconds=timeout_seconds
        )
        source_end = source["pos"] + len(source["ref"]) - 1
        forward = map_assembly_region(
            from_build,
            to_build,
            source["chrom"],
            source["pos"],
            source_end,
            timeout_seconds,
        )
        mapped = forward["mapped"]
        target_chrom = str(mapped["seq_region_name"])
        target_pos = min(int(mapped["start"]), int(mapped["end"]))
        strand = int(mapped["strand"])
        projected_ref = (
            source["ref"] if strand == 1 else reverse_complement(source["ref"])
        )
        projected_alt = (
            source["alt"] if strand == 1 else reverse_complement(source["alt"])
        )
        target_reference = fetch_reference_sequence(
            to_build,
            target_chrom,
            target_pos,
            target_pos + len(projected_ref) - 1,
            timeout_seconds,
        )
        if target_reference != projected_ref:
            raise AdapterError(
                "target_ref_mismatch",
                "The mapped source REF does not match the target assembly reference.",
            )
        target = normalize_vcf_allele(
            to_build,
            target_chrom,
            target_pos,
            projected_ref,
            projected_alt,
            timeout_seconds,
        )
        target_end = target["pos"] + len(target["ref"]) - 1
        reverse = map_assembly_region(
            to_build,
            from_build,
            target["chrom"],
            target["pos"],
            target_end,
            timeout_seconds,
        )
        roundtrip = reverse["mapped"]
        roundtrip_ok = (
            str(roundtrip["seq_region_name"]) == source["chrom"]
            and min(int(roundtrip["start"]), int(roundtrip["end"])) == source["pos"]
            and max(int(roundtrip["start"]), int(roundtrip["end"])) == source_end
        )
        if not roundtrip_ok:
            raise AdapterError(
                "liftover_roundtrip_failed",
                "Reverse assembly mapping did not recover the normalized source interval.",
            )
    except AdapterError as exc:
        service_reasons = {
            "ensembl_service_failure",
            "ensembl_response_malformed",
            "liftover_response_malformed",
            "reference_sequence_unavailable",
            "remote_rate_limited",
        }
        status = "service_failure" if exc.reason in service_reasons else "blocked"
        return remote_error_payload(
            status,
            exc.reason,
            str(exc),
            "Ensembl REST",
            [BUILD_TO_ENSEMBL_URL[from_build], BUILD_TO_ENSEMBL_URL[to_build]],
            ["chromosome", "coordinates"],
            ["sequence/region", "map"],
        ), 2 if status == "blocked" else 4

    target_notation = (
        f"chr{target['chrom']}-{target['pos']}-{target['ref']}-{target['alt']}"
    )
    return (
        {
            "schema_version": "0.1.0",
            "operation": "sequence_variant_liftover",
            "status": "liftover_ready",
            "input": {
                "asserted_notation": variant,
                "from_build": from_build,
                "to_build": to_build,
            },
            "normalized_source": source,
            "target": {**target, "notation": target_notation},
            "mapping": {
                "forward": forward,
                "strand": strand,
                "reverse": reverse,
                "roundtrip_concordant": True,
            },
            "validation": {
                "source_ref_verified": True,
                "single_contiguous_mapping": True,
                "target_ref_verified": True,
                "alleles_reverse_complemented": strand == -1,
                "normalization_applied": True,
            },
            "remote_disclosures": [
                {
                    "service": "Ensembl REST",
                    "base_urls": [
                        BUILD_TO_ENSEMBL_URL[from_build],
                        BUILD_TO_ENSEMBL_URL[to_build],
                    ],
                    "operations": ["sequence/region", "map"],
                    "fields": ["chromosome", "coordinates"],
                }
            ],
            "limitations": [
                "Only simple VCF-style SNV/indel alleles with one contiguous mapping are supported.",
                "This result is a reviewed conversion artifact, not pathogenicity evidence.",
            ],
            "provenance": {
                "service": "Ensembl REST",
                "operations": ["sequence/region", "map"],
                "retrieved_at": utc_now(),
            },
        },
        0,
    )


UPSTREAM_CLASSIFICATION_FIELDS = (
    "external_acmg",
    "acmg_classification",
    "classification",
)


def run_upstream(
    dependency: Dependency,
    script_name: str,
    arguments: Sequence[str],
    timeout_seconds: int,
) -> dict[str, Any]:
    script = dependency.skill_root / "scripts" / script_name
    minimal_environment = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "PYTHONIOENCODING": "utf-8",
    }
    try:
        result = subprocess.run(
            [sys.executable, str(script), *arguments],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            env=minimal_environment,
        )
    except subprocess.TimeoutExpired as exc:
        raise AdapterError(
            "upstream_timeout", "The upstream operation timed out."
        ) from exc
    except OSError as exc:
        raise AdapterError(
            "upstream_execution_failed", "The upstream script could not run."
        ) from exc

    if result.returncode != 0:
        stderr = result.stderr.lower()
        if script_name == "vep_annotate.py" and any(
            marker in stderr
            for marker in (
                "invalid hgvs",
                "empty vep response",
                "variant not found",
            )
        ):
            # An HTTP status alone does not establish that the asserted variant is
            # unresolved; it may represent an upstream service or request failure.
            raise AdapterError(
                "upstream_variant_unresolved",
                "Ensembl VEP rejected or could not resolve the asserted variant.",
            )
        raise AdapterError(
            "upstream_operation_failed",
            f"The upstream operation failed with exit code {result.returncode}.",
        )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise AdapterError(
            "upstream_response_malformed",
            "The upstream operation returned malformed JSON.",
        ) from exc
    if not isinstance(payload, dict):
        raise AdapterError(
            "upstream_response_malformed",
            "The upstream operation did not return a JSON object.",
        )
    return payload


def run_grch37_upstream(
    dependency: Dependency, variant: str, timeout_seconds: int
) -> dict[str, Any]:
    """Reuse the pinned VEP client/parser against Ensembl's GRCh37 endpoint."""
    bridge = Path(__file__).with_name("ensembl_grch37_adapter.py")
    upstream_script = dependency.skill_root / "scripts" / "vep_annotate.py"
    minimal_environment = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "PYTHONIOENCODING": "utf-8",
    }
    try:
        result = subprocess.run(
            [sys.executable, str(bridge), str(upstream_script), variant],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            env=minimal_environment,
        )
    except subprocess.TimeoutExpired as exc:
        raise AdapterError(
            "upstream_timeout", "The Ensembl GRCh37 operation timed out."
        ) from exc
    except OSError as exc:
        raise AdapterError(
            "upstream_execution_failed", "The Ensembl GRCh37 adapter could not run."
        ) from exc
    if result.returncode != 0:
        raise AdapterError(
            "upstream_operation_failed",
            f"The Ensembl GRCh37 operation failed with exit code {result.returncode}.",
        )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise AdapterError(
            "upstream_response_malformed",
            "The Ensembl GRCh37 operation returned malformed JSON.",
        ) from exc
    if not isinstance(payload, dict):
        raise AdapterError(
            "upstream_response_malformed",
            "The Ensembl GRCh37 operation did not return a JSON object.",
        )
    return payload


def ncbi_variation_json(path: str, timeout_seconds: int) -> dict[str, Any]:
    """Read one minimized scientific-variant response from NCBI Variation."""
    request = urllib.request.Request(
        f"{NCBI_VARIATION_URL}/{path}",
        headers={
            "Accept": "application/json",
            "User-Agent": "rare-disease-genetic-counseling/0.1",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            payload = json.load(response)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise AdapterError(
            "transcript_mapping_service_failure",
            "NCBI Variation could not resolve the asserted transcript HGVS.",
        ) from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), dict):
        raise AdapterError(
            "transcript_mapping_response_malformed",
            "NCBI Variation returned a malformed transcript-mapping response.",
        )
    return payload["data"]


def resolve_transcript_hgvs_to_grch38(
    variant: str, timeout_seconds: int
) -> dict[str, Any]:
    """Resolve versioned RefSeq transcript HGVS through an exact genomic allele."""
    if not TRANSCRIPT_HGVS_PATTERN.fullmatch(variant):
        raise AdapterError(
            "transcript_mapping_not_applicable",
            "The asserted variant is not a supported versioned RefSeq transcript HGVS.",
        )

    encoded_hgvs = urllib.parse.quote(variant, safe="")
    contextual_path = f"hgvs/{encoded_hgvs}/contextuals"
    contextual = ncbi_variation_json(contextual_path, timeout_seconds)
    spdis = contextual.get("spdis")
    if (
        contextual.get("input_hgvs_validity") != "valid"
        or not isinstance(spdis, list)
        or len(spdis) != 1
    ):
        raise AdapterError(
            "transcript_mapping_ambiguous",
            "NCBI Variation did not return exactly one valid contextual allele.",
        )
    transcript_spdi = spdis[0]
    required = ("seq_id", "position", "deleted_sequence", "inserted_sequence")
    if not isinstance(transcript_spdi, dict) or any(
        key not in transcript_spdi for key in required
    ):
        raise AdapterError(
            "transcript_mapping_response_malformed",
            "NCBI Variation returned an incomplete contextual SPDI allele.",
        )

    spdi_text = ":".join(str(transcript_spdi[key]) for key in required)
    encoded_spdi = urllib.parse.quote(spdi_text, safe="")
    canonical_path = f"spdi/{encoded_spdi}/canonical_representative"
    canonical = ncbi_variation_json(canonical_path, timeout_seconds)
    if any(key not in canonical for key in required):
        raise AdapterError(
            "transcript_mapping_response_malformed",
            "NCBI Variation returned an incomplete canonical SPDI allele.",
        )
    if not re.fullmatch(r"NC_0+[0-9]+\.[0-9]+", str(canonical["seq_id"])):
        raise AdapterError(
            "transcript_mapping_non_genomic",
            "NCBI Variation did not map the transcript allele to a genomic RefSeq accession.",
        )

    canonical_text = ":".join(str(canonical[key]) for key in required)
    encoded_canonical = urllib.parse.quote(canonical_text, safe="")
    hgvs_path = f"spdi/{encoded_canonical}/hgvs"
    genomic_hgvs_data = ncbi_variation_json(hgvs_path, timeout_seconds)
    genomic_hgvs = genomic_hgvs_data.get("hgvs")
    if not isinstance(genomic_hgvs, str) or ":g." not in genomic_hgvs:
        raise AdapterError(
            "transcript_mapping_response_malformed",
            "NCBI Variation did not return a genomic HGVS representation.",
        )

    return {
        "status": "mapped_via_canonical_allele",
        "asserted_hgvs": variant,
        "contextual_spdi": transcript_spdi,
        "canonical_genomic_spdi": canonical,
        "canonical_genomic_hgvs": genomic_hgvs,
        "annotation_input": genomic_hgvs,
        "equivalence_basis": "NCBI Variation contextual and canonical SPDI",
        "endpoints": [contextual_path, canonical_path, hgvs_path],
        "retrieved_at": utc_now(),
    }


def mapped_representation_concordance(
    annotation: dict[str, Any], mapping: dict[str, Any]
) -> bool:
    """Compare simple mapped SPDI alleles with the returned VEP representation."""
    spdi = mapping["canonical_genomic_spdi"]
    accession_match = re.fullmatch(r"NC_0*([0-9]+)\.[0-9]+", str(spdi["seq_id"]))
    if not accession_match:
        return False
    accession_number = int(accession_match.group(1))
    expected_chromosome = (
        str(accession_number)
        if 1 <= accession_number <= 22
        else "X"
        if accession_number == 23
        else "Y"
        if accession_number == 24
        else "MT"
        if accession_number == 12920
        else None
    )
    returned_chromosome = str(annotation.get("chromosome", "")).removeprefix("chr")
    if expected_chromosome is None or returned_chromosome != expected_chromosome:
        return False
    deleted = str(spdi["deleted_sequence"]).upper()
    inserted = str(spdi["inserted_sequence"]).upper()
    allele_parts = str(annotation.get("allele_string", "")).upper().split("/")
    if len(allele_parts) < 2 or annotation.get("start") != int(spdi["position"]) + 1:
        return False
    returned_ref, returned_alts = allele_parts[0], allele_parts[1:]
    if deleted and not inserted:
        return returned_ref == deleted and "-" in returned_alts
    if deleted and inserted:
        return returned_ref == deleted and inserted in returned_alts
    # VEP and SPDI use different anchoring conventions for insertions. Until the
    # adapter can reconcile both intervals exactly, an insertion is not certified.
    return False


def annotation_payload(
    variant: str,
    genome_build: str | None,
    explicit_root: str | None = None,
    timeout_seconds: int = 90,
) -> tuple[dict[str, Any], int]:
    variant = variant.strip()
    if not variant or len(variant) > 256 or any(ord(char) < 32 for char in variant):
        return error_payload(
            "blocked", "variant_input_invalid", "Variant notation is invalid."
        ), 2

    genomic = detect_genomic_variant(variant)
    genomic_hgvs = bool(GENOMIC_HGVS_PATTERN.fullmatch(variant))
    if (genomic or genomic_hgvs) and genome_build is None:
        return error_payload(
            "blocked",
            "genome_build_missing",
            "Genomic coordinates require explicit hg19 or hg38.",
        ), 2
    if genomic_hgvs:
        return error_payload(
            "blocked",
            "genomic_hgvs_requires_normalized_allele",
            "Normalize genomic HGVS to one verified VCF-style allele before annotation.",
        ), 2
    if genomic and not is_supported_simple_allele(genomic):
        return error_payload(
            "blocked",
            "variant_allele_unsupported",
            "Annotation supports non-mitochondrial SNVs and simple anchored indels only.",
        ), 2
    transcript_mapping: dict[str, Any] | None = None
    annotation_input = variant
    use_grch37 = bool(genomic and genome_build == "hg19")
    try:
        dependency = resolve_dependency(explicit_root)
    except AdapterError as exc:
        status = dependency_failure_status(exc.reason)
        return error_payload(
            status, exc.reason, str(exc)
        ), 3 if status == "capability_unavailable" else 4

    ref_alt_independently_verified = False
    if genomic:
        try:
            observed_ref = fetch_reference_sequence(
                genome_build,
                genomic["chrom"],
                genomic["pos"],
                genomic["pos"] + len(genomic["ref"]) - 1,
                timeout_seconds,
            )
        except AdapterError as exc:
            return service_error_payload(
                exc.reason,
                str(exc),
                "Ensembl REST",
                BUILD_TO_ENSEMBL_URL[genome_build],
                ["chromosome", "coordinates"],
                ["GET /sequence/region/human/{region}"],
            ), 4
        if observed_ref != genomic["ref"]:
            return remote_error_payload(
                "blocked",
                "source_ref_mismatch",
                f"REF does not match the declared {BUILD_TO_ASSEMBLY[genome_build]} reference.",
                "Ensembl REST",
                BUILD_TO_ENSEMBL_URL[genome_build],
                ["chromosome", "coordinates"],
                ["sequence/region"],
            ), 2
        ref_alt_independently_verified = True

    try:
        if use_grch37:
            annotation = run_grch37_upstream(dependency, variant, timeout_seconds)
        else:
            annotation = run_upstream(
                dependency,
                "vep_annotate.py",
                [variant, "--json", "--source", "ensembl"],
                timeout_seconds,
            )
    except AdapterError as exc:
        if not (
            TRANSCRIPT_HGVS_PATTERN.fullmatch(variant)
            and exc.reason == "upstream_variant_unresolved"
        ):
            return service_error_payload(
                exc.reason,
                str(exc),
                "Ensembl REST",
                ENSEMBL_GRCH37_REST_URL if use_grch37 else ENSEMBL_REST_URL,
                ["variant"],
                [
                    "POST /vep/human/region"
                    if genomic
                    else "POST /vep/human/hgvs"
                    if ":" in variant
                    else "POST /vep/human/id"
                ],
            ), 4
        try:
            transcript_mapping = resolve_transcript_hgvs_to_grch38(
                variant, timeout_seconds
            )
            annotation_input = transcript_mapping["annotation_input"]
            annotation = run_upstream(
                dependency,
                "vep_annotate.py",
                [annotation_input, "--json", "--source", "ensembl"],
                timeout_seconds,
            )
        except AdapterError as mapping_exc:
            service = (
                "NCBI Variation"
                if mapping_exc.reason.startswith("transcript_mapping_")
                else "Ensembl REST"
            )
            base_url = (
                NCBI_VARIATION_URL if service == "NCBI Variation" else ENSEMBL_REST_URL
            )
            fields = (
                ["scientific_variant"] if service == "NCBI Variation" else ["variant"]
            )
            failure_payload = service_error_payload(
                mapping_exc.reason,
                str(mapping_exc),
                service,
                base_url,
                fields,
                [
                    "GET /hgvs/{hgvs}/contextuals",
                    "GET /spdi/{spdi}/canonical_representative",
                    "GET /spdi/{canonical_spdi}/hgvs",
                ]
                if service == "NCBI Variation"
                else ["POST /vep/human/hgvs"],
            )
            if transcript_mapping is not None and service == "Ensembl REST":
                failure_payload["remote_disclosures"].insert(
                    0,
                    {
                        "service": "NCBI Variation",
                        "base_url": NCBI_VARIATION_URL,
                        "fields": ["scientific_variant"],
                        "operations": [
                            "GET /hgvs/{hgvs}/contextuals",
                            "GET /spdi/{spdi}/canonical_representative",
                            "GET /spdi/{canonical_spdi}/hgvs",
                        ],
                    },
                )
            return failure_payload, 4

    returned_assembly = annotation.get("assembly")
    expected_assemblies = {"GRCh37", "hg19"} if use_grch37 else {"GRCh38", "hg38"}
    assembly_concordant = returned_assembly in expected_assemblies
    representation_concordant: bool | None = None
    if genomic:
        allele_parts = str(annotation.get("allele_string", "")).upper().split("/")
        returned_chrom = str(annotation.get("chromosome", "")).removeprefix("chr")
        representation_concordant = (
            returned_chrom == genomic["chrom"]
            and annotation.get("start") == genomic["pos"]
            and len(allele_parts) >= 2
            and allele_parts[0] == genomic["ref"]
            and genomic["alt"] in allele_parts[1:]
        )
    elif transcript_mapping:
        representation_concordant = mapped_representation_concordance(
            annotation, transcript_mapping
        )

    annotation_source = annotation.get("annotation_source")
    contains_upstream_classification_fields = any(
        field in annotation for field in UPSTREAM_CLASSIFICATION_FIELDS
    )

    validation_status = "annotation_ready"
    if (
        not assembly_concordant
        or representation_concordant is False
        or (transcript_mapping is not None and representation_concordant is not True)
    ):
        validation_status = "blocked_representation_mismatch"

    return (
        {
            "schema_version": "0.1.0",
            "operation": "sequence_variant_annotation",
            "status": validation_status,
            "input": {
                "notation": variant,
                "notation_type": "genomic" if genomic else "hgvs_or_identifier",
                "declared_genome_build": genome_build,
            },
            "remote_disclosures": [
                *(
                    [
                        {
                            "service": "NCBI Variation",
                            "base_url": NCBI_VARIATION_URL,
                            "fields": ["scientific_variant"],
                            "operations": [
                                "GET /hgvs/{hgvs}/contextuals",
                                "GET /spdi/{spdi}/canonical_representative",
                                "GET /spdi/{canonical_spdi}/hgvs",
                            ],
                        }
                    ]
                    if transcript_mapping
                    else []
                ),
                {
                    "service": "Ensembl REST",
                    "base_url": ENSEMBL_GRCH37_REST_URL
                    if use_grch37
                    else ENSEMBL_REST_URL,
                    "fields": (
                        ["chromosome", "coordinates", "variant"]
                        if genomic
                        else ["variant"]
                    ),
                    "operations": (
                        [
                            "GET /sequence/region/human/{region}",
                            "POST /vep/human/region",
                        ]
                        if genomic
                        else ["POST /vep/human/hgvs"]
                        if ":" in annotation_input
                        else ["POST /vep/human/id"]
                    ),
                },
            ],
            "transcript_mapping": transcript_mapping,
            "annotation": annotation,
            "validation": {
                "returned_assembly": returned_assembly,
                "assembly_concordant": assembly_concordant,
                "returned_representation_concordant": representation_concordant,
                "ref_alt_independently_verified": ref_alt_independently_verified,
                "classification_ready": False,
                "contains_upstream_classification_fields": contains_upstream_classification_fields,
                "annotation_source": annotation_source,
                "annotation_source_expected": "ensembl",
                "annotation_source_concordant": annotation_source
                in {None, "ensembl", "ensembl_vep"},
            },
            "limitations": [
                *(
                    []
                    if ref_alt_independently_verified
                    else [
                        "This representation was not independently verified as a genomic REF/ALT allele."
                    ]
                ),
                *(
                    [
                        "Classification-shaped fields in the preserved upstream response are quarantined and must not be used as a clinical classification."
                    ]
                    if contains_upstream_classification_fields
                    else []
                ),
                *(
                    [
                        "The asserted transcript HGVS was preserved and mapped through an exact canonical genomic allele; transcript-version equivalence was not inferred from matching c. coordinates alone."
                    ]
                    if transcript_mapping
                    else []
                ),
                "Population and prediction fields require disease- and VCEP-specific interpretation.",
                "The upstream automatic classification engine was not run.",
            ],
            "provenance": provenance(
                "ensembl_grch37_adapter.py using pinned vep_annotate.py"
                if use_grch37
                else "variant-classifier/scripts/vep_annotate.py"
            ),
        },
        0 if validation_status == "annotation_ready" else 2,
    )


def vcep_payload(
    gene: str,
    explicit_root: str | None = None,
    timeout_seconds: int = 20,
) -> tuple[dict[str, Any], int]:
    gene = gene.strip().upper()
    if not GENE_PATTERN.fullmatch(gene):
        return error_payload(
            "blocked", "gene_symbol_invalid", "Gene symbol is invalid."
        ), 2
    try:
        dependency = resolve_dependency(explicit_root)
        upstream = run_upstream(
            dependency,
            "check_vcep_spec.py",
            [gene, "--json"],
            timeout_seconds,
        )
    except AdapterError as exc:
        status = dependency_failure_status(exc.reason)
        return error_payload(
            status, exc.reason, str(exc)
        ), 3 if status == "capability_unavailable" else 4

    specifications = []
    for item in upstream.get("specifications", []):
        if not isinstance(item, dict):
            continue
        sanitized = {
            key: value for key, value in item.items() if key != "guideline_path"
        }
        guideline_file = sanitized.get("guideline_file")
        sanitized["guideline_relative_path"] = (
            f"data/vcep-guidelines/{guideline_file}" if guideline_file else None
        )
        specifications.append(sanitized)

    return (
        {
            "schema_version": "0.1.0",
            "operation": "vcep_specification_lookup",
            "status": "ok",
            "gene": gene,
            "has_vcep": bool(specifications),
            "specification_count": len(specifications),
            "specifications": specifications,
            "selection_required": len(specifications) > 1,
            "limitations": [
                "Select by gene, disease, and inheritance; gene match alone is insufficient.",
                "Read the selected guideline fully before applying any modified criterion.",
            ],
            "provenance": provenance("variant-classifier/scripts/check_vcep_spec.py"),
        },
        0,
    )


def error_payload(status: str, reason: str, message: str) -> dict[str, Any]:
    return {
        "schema_version": "0.1.0",
        "status": status,
        "reason": reason,
        "message": message,
        "classification": None,
        "provenance": provenance("upstream_variant_adapter"),
    }


def remote_error_payload(
    status: str,
    reason: str,
    message: str,
    service: str,
    base_url: str | list[str],
    fields: list[str],
    operations: list[str],
) -> dict[str, Any]:
    """Preserve the actual remote service and minimized disclosure on failure."""
    disclosure: dict[str, Any] = {
        "service": service,
        "fields": fields,
        "operations": operations,
    }
    if isinstance(base_url, list):
        disclosure["base_urls"] = base_url
    else:
        disclosure["base_url"] = base_url
    return {
        "schema_version": "0.1.0",
        "status": status,
        "reason": reason,
        "message": message,
        "classification": None,
        "remote_disclosures": [disclosure],
        "provenance": {
            "service": service,
            "base_url": base_url,
            "operations": operations,
            "retrieved_at": utc_now(),
        },
    }


def service_error_payload(
    reason: str,
    message: str,
    service: str,
    base_url: str,
    fields: list[str],
    operations: list[str],
) -> dict[str, Any]:
    return remote_error_payload(
        "service_failure",
        reason,
        message,
        service,
        base_url,
        fields,
        operations,
    )


def dependency_failure_status(reason: str) -> str:
    dependency_reasons = {
        "upstream_dependency_unavailable",
        "upstream_commit_unverifiable",
        "upstream_commit_mismatch",
        "upstream_layout_invalid",
    }
    return (
        "capability_unavailable" if reason in dependency_reasons else "service_failure"
    )


def write_payload(payload: dict[str, Any], output: str | None) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if output:
        Path(output).write_text(serialized, encoding="utf-8")
    else:
        sys.stdout.write(serialized)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Safely reuse pinned variant-classifier annotation and VCEP resources."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    status = subparsers.add_parser("status", help="Verify the pinned dependency.")
    status.add_argument("--upstream-root")
    status.add_argument("--output", "-o")

    annotate = subparsers.add_parser(
        "annotate", help="Run pinned Ensembl VEP annotation."
    )
    annotate.add_argument("variant")
    annotate.add_argument("--genome-build", choices=("hg19", "hg38"))
    annotate.add_argument("--upstream-root")
    annotate.add_argument("--timeout", type=int, default=90, choices=range(1, 121))
    annotate.add_argument("--output", "-o")

    liftover = subparsers.add_parser(
        "liftover", help="Convert one simple sequence allele between GRCh37 and GRCh38."
    )
    liftover.add_argument("variant")
    liftover.add_argument("--from-build", required=True, choices=("hg19", "hg38"))
    liftover.add_argument("--to-build", required=True, choices=("hg19", "hg38"))
    liftover.add_argument("--timeout", type=int, default=30, choices=range(1, 121))
    liftover.add_argument("--output", "-o")

    vcep = subparsers.add_parser("vcep", help="Look up pinned VCEP specifications.")
    vcep.add_argument("gene")
    vcep.add_argument("--upstream-root")
    vcep.add_argument("--timeout", type=int, default=20, choices=range(1, 61))
    vcep.add_argument("--output", "-o")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "status":
        payload, exit_code = status_payload(args.upstream_root)
    elif args.command == "annotate":
        payload, exit_code = annotation_payload(
            args.variant,
            args.genome_build,
            args.upstream_root,
            args.timeout,
        )
    elif args.command == "liftover":
        payload, exit_code = liftover_payload(
            args.variant,
            args.from_build,
            args.to_build,
            args.timeout,
        )
    else:
        payload, exit_code = vcep_payload(
            args.gene,
            args.upstream_root,
            args.timeout,
        )
    write_payload(payload, args.output)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
