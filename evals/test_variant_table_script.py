#!/usr/bin/env python3
"""Focused tests for the local variant-table inspection and extraction script."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / "plugins/rare-disease-genetic-counseling/skills/review-variant-table/scripts/review_variant_table.py"
)


def inline_cell(reference: str, value: str, formula: str | None = None) -> str:
    if formula is not None:
        return f'<c r="{reference}" t="str"><f>{formula}</f><v>{value}</v></c>'
    return f'<c r="{reference}" t="inlineStr"><is><t>{value}</t></is></c>'


def numeric_cell(reference: str, value: int) -> str:
    return f'<c r="{reference}"><v>{value}</v></c>'


def worksheet(rows: list[tuple[int, list[str]]]) -> str:
    body = "".join(
        f'<row r="{row_number}">{"".join(cells)}</row>'
        for row_number, cells in rows
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"<sheetData>{body}</sheetData>"
        "</worksheet>"
    )


def create_workbook(path: Path) -> None:
    workbook = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        "<sheets>"
        '<sheet name="Summary" sheetId="1" r:id="rId1"/>'
        '<sheet name="Direct Patient Name" sheetId="2" state="hidden" r:id="rId2"/>'
        "</sheets></workbook>"
    )
    relationships = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        'Target="worksheets/sheet1.xml"/>'
        '<Relationship Id="rId2" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        'Target="worksheets/sheet2.xml"/>'
        "</Relationships>"
    )
    summary = worksheet([(1, [inline_cell("A1", "Report summary")])])
    variants = worksheet(
        [
            (1, [inline_cell("A1", "Comment")]),
            (
                2,
                [
                    inline_cell("A2", "Gene"),
                    inline_cell("B2", "Chr"),
                    inline_cell("C2", "Position"),
                    inline_cell("D2", "Ref"),
                    inline_cell("E2", "Alt"),
                    inline_cell("F2", "Classification"),
                ],
            ),
            (
                3,
                [
                    inline_cell("A3", "GENE1"),
                    inline_cell("B3", "chr1"),
                    numeric_cell("C3", 12345),
                    inline_cell("D3", "A"),
                    inline_cell("E3", "G"),
                    inline_cell("F3", "VUS", formula='IF(1=1,"VUS","")'),
                ],
            ),
        ]
    )
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", relationships)
        archive.writestr("xl/worksheets/sheet1.xml", summary)
        archive.writestr("xl/worksheets/sheet2.xml", variants)


class VariantTableScriptTests(unittest.TestCase):
    def run_script(self, *args: str, expect_success: bool = True) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            ["python3", str(SCRIPT), *args],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        if expect_success and result.returncode != 0:
            self.fail(f"script failed: {result.stderr}")
        return result

    def test_xlsx_inspection_redacts_sheet_names_and_proposes_header(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            workbook = temp / "source.xlsx"
            output = temp / "inspection.json"
            create_workbook(workbook)

            self.run_script("inspect", str(workbook), "--output", str(output))
            payload = json.loads(output.read_text(encoding="utf-8"))
            serialized = json.dumps(payload, ensure_ascii=False)

            self.assertEqual([sheet["ref"] for sheet in payload["workbook"]["sheets"]], ["sheet_1", "sheet_2"])
            self.assertNotIn("Direct Patient Name", serialized)
            self.assertIn("hidden_sheets_present", payload["workbook"]["warnings"])
            candidate = payload["workbook"]["sheets"][1]["header_candidates"][0]
            self.assertEqual(candidate["row"], 2)
            self.assertIn("chrom", candidate["matched_fields"])
            self.assertIn("ref", candidate["matched_fields"])

    def test_xlsx_extraction_preserves_formula_warning_and_lineage(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            workbook = temp / "source.xlsx"
            mapping = temp / "mapping.json"
            output = temp / "extracted.json"
            create_workbook(workbook)
            mapping.write_text(
                json.dumps(
                    {
                        "gene": "A",
                        "chrom": "B",
                        "pos": "C",
                        "ref": "D",
                        "alt": "E",
                        "classification_supplied": "F",
                    }
                ),
                encoding="utf-8",
            )

            self.run_script(
                "extract",
                str(workbook),
                "--output",
                str(output),
                "--sheet-index",
                "2",
                "--header-row",
                "2",
                "--data-start-row",
                "3",
                "--mapping",
                str(mapping),
                "--genome-build",
                "hg38",
                "--coordinate-convention",
                "1-based",
                "--sample-scope",
                "proband_only",
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            record = payload["records"][0]

            self.assertEqual(record["source_sheet"], "sheet_2")
            self.assertEqual(record["source_row"], 3)
            self.assertEqual(record["fields"]["classification_supplied"], "VUS")
            self.assertIn("formula_cell_present", record["issues"])
            self.assertEqual(payload["row_reconciliation"]["unresolved"], 1)

    def test_csv_extraction_excludes_unmapped_identifier_column(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            table = temp / "source.csv"
            mapping = temp / "mapping.json"
            output = temp / "extracted.json"
            table.write_text(
                "Patient Name,Gene,Chr,Position,Ref,Alt\nDirect Name,GENE1,chr1,12345,A,G\n",
                encoding="utf-8",
            )
            mapping.write_text(
                json.dumps({"gene": "B", "chrom": "C", "pos": "D", "ref": "E", "alt": "F"}),
                encoding="utf-8",
            )

            self.run_script(
                "extract",
                str(table),
                "--output",
                str(output),
                "--sheet-index",
                "1",
                "--header-row",
                "1",
                "--data-start-row",
                "2",
                "--mapping",
                str(mapping),
                "--genome-build",
                "hg38",
                "--coordinate-convention",
                "1-based",
                "--sample-scope",
                "proband_only",
            )
            serialized = output.read_text(encoding="utf-8")
            payload = json.loads(serialized)

            self.assertNotIn("Direct Name", serialized)
            self.assertEqual(payload["records"][0]["disposition"], "accepted")
            self.assertEqual(payload["row_reconciliation"]["accepted"], 1)


if __name__ == "__main__":
    unittest.main()
