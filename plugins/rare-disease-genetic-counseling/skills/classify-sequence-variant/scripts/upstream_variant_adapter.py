#!/usr/bin/env python3
"""Safety adapter for the pinned upstream variant-classifier resources."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence


UPSTREAM_REPOSITORY = "https://github.com/muwenbo/vcep-classification-skills"
EXPECTED_COMMIT = "05bf1f6bce4e6be04f9e52b55db1d5fee03029d9"
UPSTREAM_SKILL_RELATIVE = Path(
    "plugins/variant-classifier/skills/variant-classifier"
)
DEFAULT_VENDOR_RELATIVE = Path("vendor/vcep-classification-skills")
ENSEMBL_REST_URL = "https://rest.ensembl.org"
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
    first_line = license_file.read_text(encoding="utf-8", errors="replace").strip().splitlines()
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
                "license_status": "release_blocked_pending_standalone_license_file",
            },
            3,
        )

    guideline_count = len(list((dependency.skill_root / "data/vcep-guidelines").glob("*.md")))
    return (
        {
            "status": "ok",
            "repository": UPSTREAM_REPOSITORY,
            "commit": dependency.commit,
            "supported_operations": ["annotate", "vcep_lookup"],
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


UPSTREAM_CLASSIFICATION_FIELDS = ("external_acmg", "acmg_classification", "classification")


def strip_upstream_classification(annotation: dict[str, Any]) -> dict[str, Any]:
    """Drop upstream classification-shaped fields.

    Upstream may return automated ACMG calls (for example GeneBe's advisory
    classification). This repository never surfaces an upstream classification
    as a clinical call, so those fields are removed before the annotation is
    embedded in adapter output.
    """
    return {
        key: value
        for key, value in annotation.items()
        if key not in UPSTREAM_CLASSIFICATION_FIELDS
    }


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
        raise AdapterError("upstream_timeout", "The upstream operation timed out.") from exc
    except OSError as exc:
        raise AdapterError("upstream_execution_failed", "The upstream script could not run.") from exc

    if result.returncode != 0:
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


def annotation_payload(
    variant: str,
    genome_build: str | None,
    explicit_root: str | None = None,
    timeout_seconds: int = 90,
) -> tuple[dict[str, Any], int]:
    variant = variant.strip()
    if not variant or len(variant) > 256 or any(ord(char) < 32 for char in variant):
        return error_payload("blocked", "variant_input_invalid", "Variant notation is invalid."), 2

    genomic = detect_genomic_variant(variant)
    if genomic and genome_build is None:
        return error_payload(
            "blocked",
            "genome_build_missing",
            "Genomic coordinates require explicit hg19 or hg38.",
        ), 2
    if genomic and genome_build != "hg38":
        return error_payload(
            "blocked",
            "grch38_normalization_required",
            "Normalize and independently verify the allele on GRCh38 before VEP annotation.",
        ), 2

    try:
        dependency = resolve_dependency(explicit_root)
        annotation = run_upstream(
            dependency,
            "vep_annotate.py",
            [variant, "--json", "--source", "ensembl"],
            timeout_seconds,
        )
    except AdapterError as exc:
        status = dependency_failure_status(exc.reason)
        return error_payload(status, exc.reason, str(exc)), 3 if status == "capability_unavailable" else 4

    returned_assembly = annotation.get("assembly")
    assembly_concordant = returned_assembly in {"GRCh38", "hg38"}
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

    annotation_source = annotation.get("annotation_source")
    annotation = strip_upstream_classification(annotation)

    validation_status = "annotation_ready"
    if not assembly_concordant or representation_concordant is False:
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
            "remote_disclosure": {
                "service": "Ensembl REST",
                "base_url": ENSEMBL_REST_URL,
                "fields": ["variant"],
            },
            "annotation": annotation,
            "validation": {
                "returned_assembly": returned_assembly,
                "assembly_concordant": assembly_concordant,
                "returned_representation_concordant": representation_concordant,
                "ref_alt_independently_verified": False,
                "classification_ready": False,
                "annotation_source": annotation_source,
                "annotation_source_expected": "ensembl",
                "annotation_source_concordant": annotation_source in {None, "ensembl"},
            },
            "limitations": [
                "VEP annotation does not independently verify REF/ALT against the target assembly.",
                "Population and prediction fields require disease- and VCEP-specific interpretation.",
                "The upstream automatic classification engine was not run.",
            ],
            "provenance": provenance("variant-classifier/scripts/vep_annotate.py"),
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
        return error_payload("blocked", "gene_symbol_invalid", "Gene symbol is invalid."), 2
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
        return error_payload(status, exc.reason, str(exc)), 3 if status == "capability_unavailable" else 4

    specifications = []
    for item in upstream.get("specifications", []):
        if not isinstance(item, dict):
            continue
        sanitized = {key: value for key, value in item.items() if key != "guideline_path"}
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


def dependency_failure_status(reason: str) -> str:
    dependency_reasons = {
        "upstream_dependency_unavailable",
        "upstream_commit_unverifiable",
        "upstream_commit_mismatch",
        "upstream_layout_invalid",
    }
    return "capability_unavailable" if reason in dependency_reasons else "service_failure"


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

    annotate = subparsers.add_parser("annotate", help="Run pinned Ensembl VEP annotation.")
    annotate.add_argument("variant")
    annotate.add_argument("--genome-build", choices=("hg19", "hg38"))
    annotate.add_argument("--upstream-root")
    annotate.add_argument("--timeout", type=int, default=90, choices=range(1, 121))
    annotate.add_argument("--output", "-o")

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
