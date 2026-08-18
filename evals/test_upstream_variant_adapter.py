#!/usr/bin/env python3
"""Focused safety tests for the pinned variant-classifier adapter."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / "plugins/rare-disease-genetic-counseling/skills/classify-sequence-variant"
    / "scripts/upstream_variant_adapter.py"
)
SPEC = importlib.util.spec_from_file_location("upstream_variant_adapter", SCRIPT)
assert SPEC and SPEC.loader
ADAPTER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = ADAPTER
SPEC.loader.exec_module(ADAPTER)
UPSTREAM = ROOT / "vendor/vcep-classification-skills"
ANNOTATION_SCHEMA = (
    ROOT
    / "plugins/rare-disease-genetic-counseling/schemas/sequence-annotation.schema.json"
)


class UpstreamVariantAdapterTests(unittest.TestCase):
    def test_status_verifies_pinned_dependency_and_disables_classifier(self) -> None:
        payload, exit_code = ADAPTER.status_payload(str(UPSTREAM))
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["commit"], ADAPTER.EXPECTED_COMMIT)
        self.assertEqual(payload["supported_operations"], ["annotate", "vcep_lookup"])
        self.assertFalse(payload["classification_engine_enabled"])

    def test_explicit_missing_dependency_does_not_fall_back_to_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            payload, exit_code = ADAPTER.status_payload(temporary_directory)
        self.assertEqual(exit_code, 3)
        self.assertEqual(payload["reason"], "upstream_dependency_unavailable")

    def test_genomic_annotation_requires_build_before_subprocess(self) -> None:
        with mock.patch.object(ADAPTER, "run_upstream") as runner:
            payload, exit_code = ADAPTER.annotation_payload("chr1:100:A:G", None)
        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["reason"], "genome_build_missing")
        runner.assert_not_called()

    def test_hg19_requires_external_normalization_before_annotation(self) -> None:
        with mock.patch.object(ADAPTER, "run_upstream") as runner:
            payload, exit_code = ADAPTER.annotation_payload("chr1:100:A:G", "hg19")
        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["reason"], "grch38_normalization_required")
        runner.assert_not_called()

    def test_annotation_preserves_upstream_output_without_claiming_ref_verification(self) -> None:
        annotation = {
            "input": "1 100 . A G . . .",
            "assembly": "GRCh38",
            "chromosome": "1",
            "start": 100,
            "end": 100,
            "allele_string": "A/G",
            "most_severe_consequence": "missense_variant",
            "gene_symbol": "GENE1",
        }
        with mock.patch.object(ADAPTER, "resolve_dependency") as resolver, mock.patch.object(
            ADAPTER, "run_upstream", return_value=annotation
        ):
            resolver.return_value = ADAPTER.Dependency(
                UPSTREAM,
                UPSTREAM / ADAPTER.UPSTREAM_SKILL_RELATIVE,
                ADAPTER.EXPECTED_COMMIT,
            )
            payload, exit_code = ADAPTER.annotation_payload("chr1:100:A:G", "hg38")
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["annotation"], annotation)
        self.assertTrue(payload["validation"]["returned_representation_concordant"])
        self.assertFalse(payload["validation"]["ref_alt_independently_verified"])
        self.assertFalse(payload["validation"]["classification_ready"])
        schema = json.loads(ANNOTATION_SCHEMA.read_text(encoding="utf-8"))
        Draft202012Validator(schema).validate(payload)

    def test_annotation_pins_upstream_source_to_ensembl(self) -> None:
        annotation = {
            "assembly": "GRCh38",
            "chromosome": "1",
            "start": 100,
            "allele_string": "A/G",
            "annotation_source": "ensembl",
        }
        with mock.patch.object(ADAPTER, "resolve_dependency") as resolver, mock.patch.object(
            ADAPTER, "run_upstream", return_value=annotation
        ) as runner:
            resolver.return_value = ADAPTER.Dependency(
                UPSTREAM,
                UPSTREAM / ADAPTER.UPSTREAM_SKILL_RELATIVE,
                ADAPTER.EXPECTED_COMMIT,
            )
            payload, exit_code = ADAPTER.annotation_payload("chr1:100:A:G", "hg38")
        self.assertEqual(exit_code, 0)
        args = runner.call_args[0][2]
        self.assertIn("--source", args)
        self.assertEqual(args[args.index("--source") + 1], "ensembl")
        self.assertTrue(payload["validation"]["annotation_source_concordant"])

    def test_annotation_strips_upstream_automated_classification(self) -> None:
        annotation = {
            "assembly": "GRCh38",
            "chromosome": "1",
            "start": 100,
            "allele_string": "A/G",
            "annotation_source": "genebe",
            "external_acmg": {
                "classification": "Pathogenic",
                "source": "GeneBe automated ACMG (advisory only - not a VCEP call)",
            },
        }
        with mock.patch.object(ADAPTER, "resolve_dependency") as resolver, mock.patch.object(
            ADAPTER, "run_upstream", return_value=annotation
        ):
            resolver.return_value = ADAPTER.Dependency(
                UPSTREAM,
                UPSTREAM / ADAPTER.UPSTREAM_SKILL_RELATIVE,
                ADAPTER.EXPECTED_COMMIT,
            )
            payload, exit_code = ADAPTER.annotation_payload("chr1:100:A:G", "hg38")
        self.assertNotIn("external_acmg", payload["annotation"])
        self.assertNotIn("Pathogenic", json.dumps(payload))
        self.assertFalse(payload["validation"]["annotation_source_concordant"])
        self.assertFalse(payload["validation"]["classification_ready"])
        schema = json.loads(ANNOTATION_SCHEMA.read_text(encoding="utf-8"))
        Draft202012Validator(schema).validate(payload)

    def test_vcep_lookup_reuses_registry_and_removes_absolute_paths(self) -> None:
        payload, exit_code = ADAPTER.vcep_payload("TP53", str(UPSTREAM))
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["status"], "ok")
        self.assertTrue(payload["has_vcep"])
        self.assertGreaterEqual(payload["specification_count"], 1)
        for specification in payload["specifications"]:
            self.assertNotIn("guideline_path", specification)
            self.assertFalse(str(specification["guideline_relative_path"]).startswith("/"))

    def test_timeout_is_a_service_failure_not_an_empty_result(self) -> None:
        dependency = ADAPTER.Dependency(
            UPSTREAM,
            UPSTREAM / ADAPTER.UPSTREAM_SKILL_RELATIVE,
            ADAPTER.EXPECTED_COMMIT,
        )
        with mock.patch.object(
            ADAPTER.subprocess,
            "run",
            side_effect=subprocess.TimeoutExpired(cmd=["python"], timeout=1),
        ):
            with self.assertRaises(ADAPTER.AdapterError) as raised:
                ADAPTER.run_upstream(dependency, "vep_annotate.py", ["rs1", "--json"], 1)
        self.assertEqual(raised.exception.reason, "upstream_timeout")

    def test_failure_envelope_matches_annotation_schema(self) -> None:
        schema = json.loads(ANNOTATION_SCHEMA.read_text(encoding="utf-8"))
        payload, _exit_code = ADAPTER.annotation_payload("chr1:100:A:G", None)
        Draft202012Validator(schema).validate(payload)


if __name__ == "__main__":
    unittest.main()
