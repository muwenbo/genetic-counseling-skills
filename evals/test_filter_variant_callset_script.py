#!/usr/bin/env python3
"""Focused tests for the local variant-callset inspection and filtering script."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / "plugins/rare-disease-genetic-counseling/skills/filter-variant-callset/scripts/filter_variant_callset.py"
)

VCF = """##fileformat=VCFv4.2
##INFO=<ID=gnomad_AF,Number=A,Type=Float,Description="gnomAD popmax allele frequency">
##INFO=<ID=CSQ,Number=.,Type=String,Description="Consequence annotations from Ensembl VEP. Format: Allele|Consequence|SYMBOL|Gene">
##FORMAT=<ID=GT,Number=1,Type=String,Description="Genotype">
##FORMAT=<ID=DP,Number=1,Type=Integer,Description="Depth">
#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tPROBAND
1\t100\t.\tA\tT\t800\tPASS\tgnomad_AF=0.4;CSQ=T|missense_variant|BRCA1|ENSG1\tGT:DP\t0/1:50
2\t200\t.\tG\tC\t900\tPASS\tgnomad_AF=0.00001;CSQ=C|stop_gained|TP53|ENSG2\tGT:DP\t1/1:60
3\t300\t.\tT\tG\t40\tPASS\tCSQ=G|synonymous_variant|GENEX|ENSG3\tGT:DP\t0/1:10
4\t400\t.\tC\tA\t950\tPASS\tgnomad_AF=0.0002;CSQ=A|frameshift_variant|PKD1|ENSG4\tGT:DP\t0/1:80
"""


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", str(SCRIPT), *args],
        capture_output=True,
        text=True,
    )


class FilterCallsetScriptTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.vcf = self.tmp / "callset.vcf"
        self.vcf.write_text(VCF, encoding="utf-8")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _write_params(self, params: dict) -> Path:
        path = self.tmp / "params.json"
        path.write_text(json.dumps(params), encoding="utf-8")
        return path

    def test_inspect_proposes_candidate_fields_without_selecting(self) -> None:
        result = run("inspect", str(self.vcf))
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["format"], "vcf")
        self.assertEqual(report["variant_count"], 4)
        self.assertIn("INFO/gnomad_AF", report["candidate_fields"]["af"])
        self.assertIn("CSQ/Consequence", report["candidate_fields"]["consequence"])
        self.assertEqual(report["samples"], ["PROBAND"])

    def test_filter_funnel_and_excluded_classes(self) -> None:
        params = self._write_params(
            {
                "genome_build": "GRCh38",
                "af_field": "INFO/gnomad_AF",
                "af_max": 0.001,
                "consequence_field": "CSQ/Consequence",
                "consequence_include": [
                    "stop_gained",
                    "frameshift_variant",
                    "missense_variant",
                ],
                "gene_field": "CSQ/SYMBOL",
                "quality_field": "QUAL",
                "quality_min": 100,
            }
        )
        result = run("filter", str(self.vcf), "--params", str(params))
        self.assertEqual(result.returncode, 0, result.stderr)
        out = json.loads(result.stdout)
        self.assertEqual(out["artifact"], "variant_prioritization")
        self.assertEqual(out["funnel"]["examined"], 4)
        self.assertEqual(out["funnel"]["shortlisted"], 2)
        # Common (AF 0.4) and synonymous variants are excluded, counted not deleted.
        self.assertEqual(out["excluded_class_counts"].get("frequency"), 1)
        self.assertEqual(out["excluded_class_counts"].get("consequence"), 1)
        genes = {c["gene"] for c in out["candidates"]}
        self.assertEqual(genes, {"TP53", "PKD1"})
        # Rarest-first ordering.
        self.assertEqual(out["candidates"][0]["gene"], "TP53")

    def test_unknown_frequency_is_kept_and_counted(self) -> None:
        params = self._write_params(
            {
                "genome_build": "GRCh38",
                "af_field": "INFO/gnomad_AF",
                "af_max": 0.001,
                "keep_unknown_af": True,
                "consequence_field": "CSQ/Consequence",
                "consequence_max_rank": 20,
            }
        )
        out = json.loads(
            run("filter", str(self.vcf), "--params", str(params)).stdout
        )
        # chr3 has no gnomad_AF and a synonymous consequence within rank 20.
        self.assertEqual(out["unknown_frequency_kept"], 1)
        self.assertTrue(any(c["chrom"] == "3" for c in out["candidates"]))

    def test_homozygous_zygosity_filter(self) -> None:
        params = self._write_params(
            {
                "genome_build": "GRCh38",
                "consequence_field": "CSQ/Consequence",
                "consequence_max_rank": 20,
                "require_zygosity": "hom",
            }
        )
        out = json.loads(
            run("filter", str(self.vcf), "--params", str(params)).stdout
        )
        self.assertEqual(out["funnel"]["shortlisted"], 1)
        self.assertEqual(out["candidates"][0]["genotype_supplied"], "1/1")

    def test_missing_build_is_a_hard_stop(self) -> None:
        params = self._write_params({"af_field": "INFO/gnomad_AF"})
        result = run("filter", str(self.vcf), "--params", str(params))
        self.assertEqual(result.returncode, 2)
        self.assertIn("genome_build", result.stderr)

    def test_tsv_filter(self) -> None:
        tsv = self.tmp / "callset.tsv"
        tsv.write_text(
            "Chr\tStart\tRef\tAlt\tGene\tFunc\tgnomAD_AF\n"
            "1\t100\tA\tT\tBRCA1\tmissense_variant\t0.3\n"
            "2\t200\tG\tC\tTP53\tstop_gained\t0.00001\n",
            encoding="utf-8",
        )
        params = self._write_params(
            {
                "genome_build": "hg19",
                "af_field": "COL/gnomAD_AF",
                "af_max": 0.001,
                "consequence_field": "COL/Func",
                "consequence_include": ["stop_gained", "missense_variant"],
                "chrom_field": "COL/Chr",
                "pos_field": "COL/Start",
            }
        )
        out = json.loads(run("filter", str(tsv), "--params", str(params)).stdout)
        self.assertEqual(out["funnel"]["shortlisted"], 1)
        self.assertEqual(out["excluded_class_counts"].get("frequency"), 1)
        self.assertEqual(out["candidates"][0]["chrom"], "2")


if __name__ == "__main__":
    unittest.main()
