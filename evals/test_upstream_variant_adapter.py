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
LIFTOVER_SCHEMA = (
    ROOT
    / "plugins/rare-disease-genetic-counseling/schemas/sequence-liftover.schema.json"
)
INTERPRETATION_SCHEMA = (
    ROOT
    / "plugins/rare-disease-genetic-counseling/schemas/interpretation-proposal.schema.json"
)


class UpstreamVariantAdapterTests(unittest.TestCase):
    def test_status_verifies_pinned_dependency_and_disables_classifier(self) -> None:
        payload, exit_code = ADAPTER.status_payload(str(UPSTREAM))
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["commit"], ADAPTER.EXPECTED_COMMIT)
        self.assertEqual(
            payload["supported_operations"], ["annotate", "liftover", "vcep_lookup"]
        )
        self.assertEqual(payload["annotation_assemblies"], ["GRCh38", "GRCh37"])
        self.assertFalse(payload["classification_engine_enabled"])

    def test_explicit_missing_dependency_does_not_fall_back_to_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            payload, exit_code = ADAPTER.status_payload(temporary_directory)
        self.assertEqual(exit_code, 3)
        self.assertEqual(payload["reason"], "upstream_dependency_unavailable")

    def test_status_offers_approved_setup_when_dependency_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            payload, exit_code = ADAPTER.status_payload(temporary_directory)
        self.assertEqual(exit_code, 3)
        self.assertTrue(payload["approved_setup_available"])
        self.assertEqual(
            payload["setup_operation"], "prepare --allow-network-install"
        )

    def test_prepare_requires_explicit_network_install_approval(self) -> None:
        with (
            tempfile.TemporaryDirectory() as temporary_directory,
            mock.patch.object(ADAPTER, "run_git_command") as runner,
        ):
            payload, exit_code = ADAPTER.prepare_payload(
                False, temporary_directory
            )
        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["reason"], "dependency_install_not_approved")
        runner.assert_not_called()

    def test_prepare_installs_only_verified_commit_in_selected_cache(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            cache_root = Path(temporary_directory) / "cache"

            def create_checkout(arguments, _timeout_seconds):
                if arguments[:2] == ["init", "--quiet"]:
                    checkout = Path(arguments[2])
                    skill_root = checkout / ADAPTER.UPSTREAM_SKILL_RELATIVE
                    (skill_root / "scripts").mkdir(parents=True)
                    (skill_root / "data").mkdir()
                    (skill_root / "scripts/vep_annotate.py").write_text("")
                    (skill_root / "scripts/check_vcep_spec.py").write_text("")
                    (skill_root / "data/vcep_registry.json").write_text("{}")
                    (checkout / "LICENSE").write_text("MIT License\n")

            with (
                mock.patch.object(
                    ADAPTER, "run_git_command", side_effect=create_checkout
                ) as runner,
                mock.patch.object(
                    ADAPTER, "git_commit", return_value=ADAPTER.EXPECTED_COMMIT
                ),
            ):
                payload, exit_code = ADAPTER.prepare_payload(
                    True, str(cache_root), timeout_seconds=30
                )

            self.assertEqual(exit_code, 0)
            self.assertEqual(payload["status"], "ok")
            self.assertEqual(payload["commit"], ADAPTER.EXPECTED_COMMIT)
            self.assertFalse(payload["already_present"])
            self.assertFalse(
                payload["remote_disclosures"][0]["clinical_data_disclosed"]
            )
            self.assertEqual(runner.call_count, 4)
            installed = cache_root / ADAPTER.PINNED_CHECKOUT_DIRECTORY
            self.assertTrue(installed.is_dir())

    def test_prepare_does_not_overwrite_an_invalid_cache_target(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            target = (
                Path(temporary_directory) / ADAPTER.PINNED_CHECKOUT_DIRECTORY
            )
            target.mkdir()
            marker = target / "keep.txt"
            marker.write_text("user data")
            with mock.patch.object(ADAPTER, "run_git_command") as runner:
                payload, exit_code = ADAPTER.prepare_payload(
                    True, temporary_directory
                )
            self.assertEqual(exit_code, 2)
            self.assertEqual(payload["reason"], "dependency_cache_conflict")
            self.assertEqual(marker.read_text(), "user data")
            runner.assert_not_called()

    def test_missing_dependency_stops_before_reference_service(self) -> None:
        with (
            tempfile.TemporaryDirectory() as temporary_directory,
            mock.patch.object(ADAPTER, "fetch_reference_sequence") as fetcher,
        ):
            payload, exit_code = ADAPTER.annotation_payload(
                "chr1:100:A:G", "hg38", temporary_directory
            )
        self.assertEqual(exit_code, 3)
        self.assertEqual(payload["reason"], "upstream_dependency_unavailable")
        fetcher.assert_not_called()

    def test_genomic_annotation_requires_build_before_subprocess(self) -> None:
        with mock.patch.object(ADAPTER, "run_upstream") as runner:
            payload, exit_code = ADAPTER.annotation_payload("chr1:100:A:G", None)
        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["reason"], "genome_build_missing")
        runner.assert_not_called()

    def test_genomic_refseq_hgvs_requires_build_before_subprocess(self) -> None:
        with mock.patch.object(ADAPTER, "resolve_dependency") as resolver:
            payload, exit_code = ADAPTER.annotation_payload(
                "NC_000001.11:g.100A>G", None
            )
        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["reason"], "genome_build_missing")
        resolver.assert_not_called()

    def test_genomic_refseq_hgvs_requires_normalized_allele(self) -> None:
        with mock.patch.object(ADAPTER, "resolve_dependency") as resolver:
            payload, exit_code = ADAPTER.annotation_payload(
                "NC_000001.11:g.100A>G", "hg38"
            )
        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["reason"], "genomic_hgvs_requires_normalized_allele")
        resolver.assert_not_called()

    def test_annotation_rejects_mitochondrial_and_complex_vcf_alleles(self) -> None:
        for variant in ("chrMT:100:A:G", "chr1:100:AC:GT", "chr1:100:AC:GTT"):
            with (
                self.subTest(variant=variant),
                mock.patch.object(ADAPTER, "resolve_dependency") as resolver,
            ):
                payload, exit_code = ADAPTER.annotation_payload(variant, "hg38")
            self.assertEqual(exit_code, 2)
            self.assertEqual(payload["reason"], "variant_allele_unsupported")
            resolver.assert_not_called()

    def test_hg19_requires_external_normalization_before_annotation(self) -> None:
        annotation = {
            "assembly": "GRCh37",
            "chromosome": "4",
            "start": 1808989,
            "allele_string": "A/T",
            "annotation_source": "ensembl_vep",
        }
        dependency = ADAPTER.Dependency(
            UPSTREAM,
            UPSTREAM / ADAPTER.UPSTREAM_SKILL_RELATIVE,
            ADAPTER.EXPECTED_COMMIT,
        )
        with (
            mock.patch.object(ADAPTER, "resolve_dependency", return_value=dependency),
            mock.patch.object(
                ADAPTER, "run_grch37_upstream", return_value=annotation
            ) as runner,
            mock.patch.object(ADAPTER, "fetch_reference_sequence", return_value="A"),
        ):
            payload, exit_code = ADAPTER.annotation_payload("chr1:100:A:G", "hg19")
        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["status"], "blocked_representation_mismatch")
        runner.assert_called_once()

    def test_hg19_routes_to_ensembl_grch37_and_preserves_assembly(self) -> None:
        annotation = {
            "assembly": "GRCh37",
            "chromosome": "4",
            "start": 1808989,
            "allele_string": "A/T",
            "annotation_source": "ensembl_vep",
            "most_severe_consequence": "stop_gained",
        }
        dependency = ADAPTER.Dependency(
            UPSTREAM,
            UPSTREAM / ADAPTER.UPSTREAM_SKILL_RELATIVE,
            ADAPTER.EXPECTED_COMMIT,
        )
        with (
            mock.patch.object(ADAPTER, "resolve_dependency", return_value=dependency),
            mock.patch.object(
                ADAPTER, "run_grch37_upstream", return_value=annotation
            ) as runner,
            mock.patch.object(ADAPTER, "run_upstream") as grch38_runner,
            mock.patch.object(ADAPTER, "fetch_reference_sequence", return_value="A"),
        ):
            payload, exit_code = ADAPTER.annotation_payload("chr4-1808989-A-T", "hg19")

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["status"], "annotation_ready")
        self.assertEqual(payload["validation"]["returned_assembly"], "GRCh37")
        self.assertTrue(payload["validation"]["assembly_concordant"])
        self.assertTrue(payload["validation"]["returned_representation_concordant"])
        self.assertEqual(
            payload["remote_disclosures"][-1]["base_url"],
            "https://grch37.rest.ensembl.org",
        )
        runner.assert_called_once_with(dependency, "chr4-1808989-A-T", 90)
        grch38_runner.assert_not_called()

    def test_annotation_preserves_upstream_output_after_independent_ref_check(
        self,
    ) -> None:
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
        with (
            mock.patch.object(ADAPTER, "resolve_dependency") as resolver,
            mock.patch.object(ADAPTER, "run_upstream", return_value=annotation),
            mock.patch.object(ADAPTER, "fetch_reference_sequence", return_value="A"),
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
        self.assertTrue(payload["validation"]["ref_alt_independently_verified"])
        self.assertFalse(payload["validation"]["classification_ready"])
        schema = json.loads(ANNOTATION_SCHEMA.read_text(encoding="utf-8"))
        Draft202012Validator(schema).validate(payload)

    def test_annotation_pins_upstream_source_to_ensembl(self) -> None:
        annotation = {
            "assembly": "GRCh38",
            "chromosome": "1",
            "start": 100,
            "allele_string": "A/G",
            "annotation_source": "ensembl_vep",
        }
        with (
            mock.patch.object(ADAPTER, "resolve_dependency") as resolver,
            mock.patch.object(
                ADAPTER, "run_upstream", return_value=annotation
            ) as runner,
            mock.patch.object(ADAPTER, "fetch_reference_sequence", return_value="A"),
        ):
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

    def test_old_refseq_transcript_falls_back_through_exact_ncbi_genomic_allele(
        self,
    ) -> None:
        mapping = {
            "status": "mapped_via_canonical_allele",
            "asserted_hgvs": "NM_004006.2:c.6787del",
            "contextual_spdi": {
                "seq_id": "NM_004006.2",
                "position": 7030,
                "deleted_sequence": "C",
                "inserted_sequence": "",
            },
            "canonical_genomic_spdi": {
                "seq_id": "NC_000023.11",
                "position": 31929720,
                "deleted_sequence": "G",
                "inserted_sequence": "",
            },
            "canonical_genomic_hgvs": "NC_000023.11:g.31929721del",
            "annotation_input": "NC_000023.11:g.31929721del",
            "equivalence_basis": "NCBI Variation contextual and canonical SPDI",
            "endpoints": [],
            "retrieved_at": "2026-08-19T00:00:00Z",
        }
        annotation = {
            "assembly": "GRCh38",
            "chromosome": "X",
            "start": 31929721,
            "allele_string": "G/-",
            "annotation_source": "ensembl",
            "canonical_transcript": {"transcript_id": "NM_004006.3"},
        }
        dependency = ADAPTER.Dependency(
            UPSTREAM,
            UPSTREAM / ADAPTER.UPSTREAM_SKILL_RELATIVE,
            ADAPTER.EXPECTED_COMMIT,
        )
        with (
            mock.patch.object(ADAPTER, "resolve_dependency", return_value=dependency),
            mock.patch.object(
                ADAPTER,
                "run_upstream",
                side_effect=[
                    ADAPTER.AdapterError(
                        "upstream_variant_unresolved", "old transcript unavailable"
                    ),
                    annotation,
                ],
            ) as runner,
            mock.patch.object(
                ADAPTER, "resolve_transcript_hgvs_to_grch38", return_value=mapping
            ),
        ):
            payload, exit_code = ADAPTER.annotation_payload(
                "NM_004006.2:c.6787del", None
            )

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["input"]["notation"], "NM_004006.2:c.6787del")
        self.assertEqual(
            payload["transcript_mapping"]["annotation_input"],
            mapping["annotation_input"],
        )
        self.assertTrue(payload["validation"]["returned_representation_concordant"])
        self.assertEqual(
            runner.call_args_list[1].args[2][0], "NC_000023.11:g.31929721del"
        )
        self.assertEqual(
            [item["service"] for item in payload["remote_disclosures"]],
            ["NCBI Variation", "Ensembl REST"],
        )
        schema = json.loads(ANNOTATION_SCHEMA.read_text(encoding="utf-8"))
        Draft202012Validator(schema).validate(payload)

    def test_old_refseq_fallback_blocks_wrong_chromosome_annotation(self) -> None:
        mapping = {
            "status": "mapped_via_canonical_allele",
            "asserted_hgvs": "NM_000001.1:c.1A>G",
            "contextual_spdi": {
                "seq_id": "NM_000001.1",
                "position": 0,
                "deleted_sequence": "A",
                "inserted_sequence": "G",
            },
            "canonical_genomic_spdi": {
                "seq_id": "NC_000001.11",
                "position": 100,
                "deleted_sequence": "A",
                "inserted_sequence": "G",
            },
            "canonical_genomic_hgvs": "NC_000001.11:g.101A>G",
            "annotation_input": "NC_000001.11:g.101A>G",
            "equivalence_basis": "NCBI Variation contextual and canonical SPDI",
            "endpoints": [],
            "retrieved_at": "2026-08-19T00:00:00Z",
        }
        wrong_annotation = {
            "assembly": "GRCh38",
            "chromosome": "7",
            "start": 101,
            "allele_string": "A/G",
            "annotation_source": "ensembl_vep",
        }
        dependency = ADAPTER.Dependency(
            UPSTREAM,
            UPSTREAM / ADAPTER.UPSTREAM_SKILL_RELATIVE,
            ADAPTER.EXPECTED_COMMIT,
        )
        with (
            mock.patch.object(ADAPTER, "resolve_dependency", return_value=dependency),
            mock.patch.object(
                ADAPTER,
                "run_upstream",
                side_effect=[
                    ADAPTER.AdapterError("upstream_variant_unresolved", "unresolved"),
                    wrong_annotation,
                ],
            ),
            mock.patch.object(
                ADAPTER, "resolve_transcript_hgvs_to_grch38", return_value=mapping
            ),
        ):
            payload, exit_code = ADAPTER.annotation_payload("NM_000001.1:c.1A>G", None)
        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["status"], "blocked_representation_mismatch")
        self.assertFalse(payload["validation"]["returned_representation_concordant"])

    def test_annotation_preserves_but_quarantines_upstream_classification(self) -> None:
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
        with (
            mock.patch.object(ADAPTER, "resolve_dependency") as resolver,
            mock.patch.object(ADAPTER, "run_upstream", return_value=annotation),
            mock.patch.object(ADAPTER, "fetch_reference_sequence", return_value="A"),
        ):
            resolver.return_value = ADAPTER.Dependency(
                UPSTREAM,
                UPSTREAM / ADAPTER.UPSTREAM_SKILL_RELATIVE,
                ADAPTER.EXPECTED_COMMIT,
            )
            payload, exit_code = ADAPTER.annotation_payload("chr1:100:A:G", "hg38")
        self.assertEqual(payload["annotation"], annotation)
        self.assertTrue(
            payload["validation"]["contains_upstream_classification_fields"]
        )
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
            self.assertFalse(
                str(specification["guideline_relative_path"]).startswith("/")
            )

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
                ADAPTER.run_upstream(
                    dependency, "vep_annotate.py", ["rs1", "--json"], 1
                )
        self.assertEqual(raised.exception.reason, "upstream_timeout")

    def test_generic_vep_http_400_is_not_treated_as_unresolved_variant(self) -> None:
        dependency = ADAPTER.Dependency(
            UPSTREAM,
            UPSTREAM / ADAPTER.UPSTREAM_SKILL_RELATIVE,
            ADAPTER.EXPECTED_COMMIT,
        )
        completed = subprocess.CompletedProcess(
            args=["python"],
            returncode=1,
            stdout="",
            stderr="400 Client Error: Bad Request for url",
        )
        with mock.patch.object(ADAPTER.subprocess, "run", return_value=completed):
            with self.assertRaises(ADAPTER.AdapterError) as raised:
                ADAPTER.run_upstream(
                    dependency, "vep_annotate.py", ["NM_1.1:c.1A>G"], 1
                )
        self.assertEqual(raised.exception.reason, "upstream_operation_failed")

    def test_explicit_empty_vep_response_is_an_unresolved_variant(self) -> None:
        dependency = ADAPTER.Dependency(
            UPSTREAM,
            UPSTREAM / ADAPTER.UPSTREAM_SKILL_RELATIVE,
            ADAPTER.EXPECTED_COMMIT,
        )
        completed = subprocess.CompletedProcess(
            args=["python"],
            returncode=1,
            stdout="",
            stderr="ValueError: Empty VEP response",
        )
        with mock.patch.object(ADAPTER.subprocess, "run", return_value=completed):
            with self.assertRaises(ADAPTER.AdapterError) as raised:
                ADAPTER.run_upstream(
                    dependency, "vep_annotate.py", ["NM_1.1:c.1A>G"], 1
                )
        self.assertEqual(raised.exception.reason, "upstream_variant_unresolved")

    def test_transcript_timeout_does_not_trigger_ncbi_fallback(self) -> None:
        dependency = ADAPTER.Dependency(
            UPSTREAM,
            UPSTREAM / ADAPTER.UPSTREAM_SKILL_RELATIVE,
            ADAPTER.EXPECTED_COMMIT,
        )
        with (
            mock.patch.object(ADAPTER, "resolve_dependency", return_value=dependency),
            mock.patch.object(
                ADAPTER,
                "run_upstream",
                side_effect=ADAPTER.AdapterError("upstream_timeout", "timed out"),
            ),
            mock.patch.object(ADAPTER, "resolve_transcript_hgvs_to_grch38") as mapper,
        ):
            payload, exit_code = ADAPTER.annotation_payload(
                "NM_004006.2:c.6787del", None
            )
        self.assertEqual(exit_code, 4)
        self.assertEqual(payload["status"], "service_failure")
        self.assertEqual(payload["reason"], "upstream_timeout")
        mapper.assert_not_called()

    def test_post_mapping_vep_failure_preserves_ncbi_disclosure(self) -> None:
        mapping = {
            "status": "mapped_via_canonical_allele",
            "asserted_hgvs": "NM_004006.2:c.6787del",
            "contextual_spdi": {},
            "canonical_genomic_spdi": {},
            "canonical_genomic_hgvs": "NC_000023.11:g.31929721del",
            "annotation_input": "NC_000023.11:g.31929721del",
            "equivalence_basis": "NCBI Variation contextual and canonical SPDI",
            "endpoints": [],
            "retrieved_at": "2026-08-19T00:00:00Z",
        }
        dependency = ADAPTER.Dependency(
            UPSTREAM,
            UPSTREAM / ADAPTER.UPSTREAM_SKILL_RELATIVE,
            ADAPTER.EXPECTED_COMMIT,
        )
        with (
            mock.patch.object(ADAPTER, "resolve_dependency", return_value=dependency),
            mock.patch.object(
                ADAPTER,
                "run_upstream",
                side_effect=[
                    ADAPTER.AdapterError("upstream_variant_unresolved", "unresolved"),
                    ADAPTER.AdapterError("upstream_timeout", "timed out"),
                ],
            ),
            mock.patch.object(
                ADAPTER, "resolve_transcript_hgvs_to_grch38", return_value=mapping
            ),
        ):
            payload, exit_code = ADAPTER.annotation_payload(
                "NM_004006.2:c.6787del", None
            )
        self.assertEqual(exit_code, 4)
        self.assertEqual(
            [item["service"] for item in payload["remote_disclosures"]],
            ["NCBI Variation", "Ensembl REST"],
        )

    def test_mapped_concordance_requires_chromosome_and_checkable_allele(self) -> None:
        substitution = {
            "canonical_genomic_spdi": {
                "seq_id": "NC_000001.11",
                "position": 100,
                "deleted_sequence": "A",
                "inserted_sequence": "G",
            }
        }
        wrong_chromosome = {
            "chromosome": "7",
            "start": 101,
            "allele_string": "A/G",
        }
        self.assertFalse(
            ADAPTER.mapped_representation_concordance(wrong_chromosome, substitution)
        )

        insertion = {
            "canonical_genomic_spdi": {
                "seq_id": "NC_000001.11",
                "position": 100,
                "deleted_sequence": "",
                "inserted_sequence": "T",
            }
        }
        insertion_annotation = {
            "chromosome": "1",
            "start": 101,
            "allele_string": "-/T",
        }
        self.assertFalse(
            ADAPTER.mapped_representation_concordance(insertion_annotation, insertion)
        )

    def test_genomic_ref_mismatch_stops_before_vep(self) -> None:
        dependency = ADAPTER.Dependency(
            UPSTREAM,
            UPSTREAM / ADAPTER.UPSTREAM_SKILL_RELATIVE,
            ADAPTER.EXPECTED_COMMIT,
        )
        with (
            mock.patch.object(ADAPTER, "resolve_dependency", return_value=dependency),
            mock.patch.object(ADAPTER, "fetch_reference_sequence", return_value="G"),
            mock.patch.object(ADAPTER, "run_upstream") as runner,
        ):
            payload, exit_code = ADAPTER.annotation_payload("chr1:100:A:G", "hg38")
        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["reason"], "source_ref_mismatch")
        runner.assert_not_called()

    def test_failure_envelope_matches_annotation_schema(self) -> None:
        schema = json.loads(ANNOTATION_SCHEMA.read_text(encoding="utf-8"))
        payload, _exit_code = ADAPTER.annotation_payload("chr1:100:A:G", None)
        Draft202012Validator(schema).validate(payload)

    def test_liftover_verifies_both_references_and_roundtrip(self) -> None:
        source = {"chrom": "4", "pos": 1808989, "ref": "A", "alt": "T"}
        target = {"chrom": "4", "pos": 1807262, "ref": "A", "alt": "T"}
        forward = {
            "mapped": {
                "assembly": "GRCh38",
                "seq_region_name": "4",
                "start": 1807262,
                "end": 1807262,
                "strand": 1,
            }
        }
        reverse = {
            "mapped": {
                "assembly": "GRCh37",
                "seq_region_name": "4",
                "start": 1808989,
                "end": 1808989,
                "strand": 1,
            }
        }
        with (
            mock.patch.object(
                ADAPTER, "normalize_vcf_allele", side_effect=[source, target]
            ) as normalizer,
            mock.patch.object(
                ADAPTER, "map_assembly_region", side_effect=[forward, reverse]
            ) as mapper,
            mock.patch.object(ADAPTER, "fetch_reference_sequence", return_value="A"),
        ):
            payload, exit_code = ADAPTER.liftover_payload(
                "chr4-1808989-A-T", "hg19", "hg38"
            )

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["status"], "liftover_ready")
        self.assertEqual(payload["target"]["notation"], "chr4-1807262-A-T")
        self.assertTrue(payload["mapping"]["roundtrip_concordant"])
        self.assertTrue(payload["validation"]["source_ref_verified"])
        self.assertTrue(payload["validation"]["target_ref_verified"])
        self.assertEqual(
            payload["remote_disclosures"][0]["fields"],
            ["chromosome", "coordinates"],
        )
        self.assertEqual(normalizer.call_count, 2)
        self.assertEqual(mapper.call_count, 2)
        schema = json.loads(LIFTOVER_SCHEMA.read_text(encoding="utf-8"))
        Draft202012Validator(schema).validate(payload)

    def test_liftover_blocks_multiple_mappings(self) -> None:
        with mock.patch.object(
            ADAPTER,
            "ensembl_json",
            return_value={"mappings": [{"mapped": {}}, {"mapped": {}}]},
        ):
            with self.assertRaises(ADAPTER.AdapterError) as raised:
                ADAPTER.map_assembly_region("hg19", "hg38", "1", 100, 100, 30)
        self.assertEqual(raised.exception.reason, "liftover_mapping_ambiguous")

    def test_liftover_blocks_source_ref_mismatch(self) -> None:
        with mock.patch.object(ADAPTER, "fetch_reference_sequence", return_value="G"):
            with self.assertRaises(ADAPTER.AdapterError) as raised:
                ADAPTER.normalize_vcf_allele("hg19", "1", 100, "A", "T", 30)
        self.assertEqual(raised.exception.reason, "source_ref_mismatch")

    def test_liftover_rejects_mitochondrial_and_complex_alleles(self) -> None:
        for variant in ("chrMT:100:A:G", "chr1:100:AC:GT", "chr1:100:AC:GTT"):
            with (
                self.subTest(variant=variant),
                mock.patch.object(ADAPTER, "fetch_reference_sequence") as fetcher,
            ):
                payload, exit_code = ADAPTER.liftover_payload(variant, "hg19", "hg38")
            self.assertEqual(exit_code, 2)
            self.assertEqual(payload["status"], "blocked")
            self.assertEqual(payload["reason"], "liftover_allele_unsupported")
            fetcher.assert_not_called()

    def test_liftover_rate_limit_envelope_matches_schema(self) -> None:
        with mock.patch.object(
            ADAPTER,
            "normalize_vcf_allele",
            side_effect=ADAPTER.AdapterError(
                "remote_rate_limited", "Ensembl rate-limited the request."
            ),
        ):
            payload, exit_code = ADAPTER.liftover_payload(
                "chr1:100:A:G", "hg19", "hg38"
            )
        self.assertEqual(exit_code, 4)
        self.assertEqual(payload["status"], "service_failure")
        schema = json.loads(LIFTOVER_SCHEMA.read_text(encoding="utf-8"))
        Draft202012Validator(schema).validate(payload)

    def test_liftover_blocks_target_ref_mismatch(self) -> None:
        source = {"chrom": "4", "pos": 1808989, "ref": "A", "alt": "T"}
        forward = {
            "mapped": {
                "assembly": "GRCh38",
                "seq_region_name": "4",
                "start": 1807262,
                "end": 1807262,
                "strand": 1,
            }
        }
        with (
            mock.patch.object(ADAPTER, "normalize_vcf_allele", return_value=source),
            mock.patch.object(ADAPTER, "map_assembly_region", return_value=forward),
            mock.patch.object(ADAPTER, "fetch_reference_sequence", return_value="G"),
        ):
            payload, exit_code = ADAPTER.liftover_payload(
                "chr4-1808989-A-T", "hg19", "hg38"
            )
        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["reason"], "target_ref_mismatch")

    def test_liftover_reverse_strand_reverse_complements_alleles(self) -> None:
        source = {"chrom": "1", "pos": 100, "ref": "A", "alt": "G"}
        target = {"chrom": "1", "pos": 200, "ref": "T", "alt": "C"}
        forward = {
            "mapped": {
                "assembly": "GRCh38",
                "seq_region_name": "1",
                "start": 200,
                "end": 200,
                "strand": -1,
            }
        }
        reverse = {
            "mapped": {
                "assembly": "GRCh37",
                "seq_region_name": "1",
                "start": 100,
                "end": 100,
                "strand": -1,
            }
        }
        with (
            mock.patch.object(
                ADAPTER, "normalize_vcf_allele", side_effect=[source, target]
            ) as normalizer,
            mock.patch.object(
                ADAPTER, "map_assembly_region", side_effect=[forward, reverse]
            ),
            mock.patch.object(ADAPTER, "fetch_reference_sequence", return_value="T"),
        ):
            payload, exit_code = ADAPTER.liftover_payload(
                "chr1:100:A:G", "hg19", "hg38"
            )
        self.assertEqual(exit_code, 0)
        self.assertEqual(normalizer.call_args_list[1].args[3:5], ("T", "C"))
        self.assertTrue(payload["validation"]["alleles_reverse_complemented"])

    def test_liftover_blocks_failed_reverse_mapping(self) -> None:
        source = {"chrom": "4", "pos": 100, "ref": "A", "alt": "G"}
        target = {"chrom": "4", "pos": 200, "ref": "A", "alt": "G"}
        forward = {
            "mapped": {
                "assembly": "GRCh38",
                "seq_region_name": "4",
                "start": 200,
                "end": 200,
                "strand": 1,
            }
        }
        wrong_reverse = {
            "mapped": {
                "assembly": "GRCh37",
                "seq_region_name": "4",
                "start": 101,
                "end": 101,
                "strand": 1,
            }
        }
        with (
            mock.patch.object(
                ADAPTER, "normalize_vcf_allele", side_effect=[source, target]
            ),
            mock.patch.object(
                ADAPTER, "map_assembly_region", side_effect=[forward, wrong_reverse]
            ),
            mock.patch.object(ADAPTER, "fetch_reference_sequence", return_value="A"),
        ):
            payload, exit_code = ADAPTER.liftover_payload(
                "chr4:100:A:G", "hg19", "hg38"
            )
        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["reason"], "liftover_roundtrip_failed")

    def test_simple_indel_normalization_left_aligns_homopolymer(self) -> None:
        with mock.patch.object(
            ADAPTER,
            "fetch_reference_sequence",
            side_effect=lambda _build, _chrom, start, end, _timeout: (
                "A" * (end - start + 1)
            ),
        ):
            normalized = ADAPTER.normalize_vcf_allele("hg38", "1", 3, "A", "AA", 30)
        self.assertEqual(normalized, {"chrom": "1", "pos": 1, "ref": "A", "alt": "AA"})

    def test_ensembl_rate_limit_is_service_failure(self) -> None:
        error = __import__("urllib.error").error.HTTPError(
            "https://rest.ensembl.org", 429, "Too Many Requests", {}, None
        )
        with mock.patch.object(ADAPTER.urllib.request, "urlopen", side_effect=error):
            with self.assertRaises(ADAPTER.AdapterError) as raised:
                ADAPTER.ensembl_json(
                    ADAPTER.ENSEMBL_REST_URL, "sequence/region/human/1:1..1:1", 1
                )
        self.assertEqual(raised.exception.reason, "remote_rate_limited")

    def test_ncbi_ambiguous_contextual_mapping_stops(self) -> None:
        with mock.patch.object(
            ADAPTER,
            "ncbi_variation_json",
            return_value={"input_hgvs_validity": "valid", "spdis": []},
        ):
            with self.assertRaises(ADAPTER.AdapterError) as raised:
                ADAPTER.resolve_transcript_hgvs_to_grch38("NM_004006.2:c.6787del", 30)
        self.assertEqual(raised.exception.reason, "transcript_mapping_ambiguous")

    def test_remote_service_failure_envelope_matches_annotation_schema(self) -> None:
        dependency = ADAPTER.Dependency(
            UPSTREAM,
            UPSTREAM / ADAPTER.UPSTREAM_SKILL_RELATIVE,
            ADAPTER.EXPECTED_COMMIT,
        )
        with (
            mock.patch.object(ADAPTER, "resolve_dependency", return_value=dependency),
            mock.patch.object(
                ADAPTER,
                "run_upstream",
                side_effect=ADAPTER.AdapterError("upstream_timeout", "timed out"),
            ),
        ):
            payload, exit_code = ADAPTER.annotation_payload("rs123", None)
        self.assertEqual(exit_code, 4)
        self.assertEqual(payload["provenance"]["service"], "Ensembl REST")
        schema = json.loads(ANNOTATION_SCHEMA.read_text(encoding="utf-8"))
        Draft202012Validator(schema).validate(payload)

    def test_interpretation_schema_accepts_required_sequence_tally_fields(self) -> None:
        schema = json.loads(INTERPRETATION_SCHEMA.read_text(encoding="utf-8"))
        proposal = {
            "schema_version": "0.1.0",
            "proposal_type": "sequence_classification",
            "status": "ready_for_review",
            "review_required": True,
            "scoring_framework": {
                "name": "Bayesian ACMG/AMP point calibration",
                "version": "Tavtigian et al. 2020",
                "thresholds": {"Likely pathogenic": "6-9"},
            },
            "pathogenic_subtotal": 6,
            "benign_subtotal": 0,
            "signed_total": 6,
            "rule_based_tier": "Likely pathogenic",
            "proposed_tier": "Likely pathogenic",
            "scoring_discrepancy": None,
            "evidence": [
                {
                    "criterion": "PM2",
                    "state": "met",
                    "original_strength": "moderate",
                    "effective_strength": "supporting",
                    "points": 1,
                    "evidence": "Reviewed population evidence",
                    "rationale": "Threshold met for the resolved context.",
                    "limitations_or_missing_confirmation": None,
                    "confirmation_status": "reviewed",
                    "direction": "pathogenic",
                    "source_type": "database",
                    "source_ref": "example",
                }
            ],
            "limitations": [],
            "provenance": [],
        }
        Draft202012Validator(schema).validate(proposal)


if __name__ == "__main__":
    unittest.main()
