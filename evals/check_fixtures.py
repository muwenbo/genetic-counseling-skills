#!/usr/bin/env python3
"""Validate fixture integrity without calling clinical services."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def load(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def main() -> None:
    manifest = load(ROOT / "manifest.json")
    fixtures = {item["id"]: item for item in manifest["fixtures"]}
    assert len(fixtures) == len(manifest["fixtures"]), "fixture IDs must be unique"

    loaded: dict[str, tuple[dict, dict]] = {}
    for fixture_id, item in fixtures.items():
        input_path = ROOT / item["input"]
        expected_path = ROOT / item["expected"]
        assert input_path.is_file(), f"missing input for {fixture_id}"
        assert expected_path.is_file(), f"missing expected result for {fixture_id}"
        loaded[fixture_id] = (load(input_path), load(expected_path))

    seq_input, seq_expected = loaded["SEQ-001-missing-build"]
    assert seq_input["genome_build"] is None
    assert seq_expected["outcome"] == "blocked"
    assert "assume hg38" in seq_expected["must_not"]
    assert "produce a classification tier" in seq_expected["must_not"]

    cnv_input, cnv_expected = loaded["CNV-001-missing-build"]
    parsed = cnv_expected["parsed"]
    assert cnv_input["genome_build"] is None
    assert cnv_expected["outcome"] == "blocked"
    assert parsed["inclusive_size_bp"] == parsed["end"] - parsed["start"] + 1
    assert "call the CNV Classification API" in cnv_expected["must_not"]

    _case_input, case_expected = loaded["CASE-001-infant-immunodeficiency"]
    fungal = [
        item
        for item in case_expected["required_observations"]
        if "fungal pneumonia" in item["label_contains"]
    ]
    assert fungal == [
        {
            "label_contains": "fungal pneumonia",
            "assertion": "suspected",
            "temporality": "current",
        }
    ]
    assert "diagnose an immunodeficiency syndrome" in case_expected["must_not"]
    assert "combine this case with either variant fixture" in case_expected["must_not"]

    table_input, table_expected = loaded["TABLE-001-ambiguous-layout"]
    assert table_input["selected_sheet"] is None
    assert table_input["genome_build"] is None
    assert table_expected["outcome"] == "blocked"
    assert "variant_sheet_ambiguous" in table_expected["blocking_reasons"]
    assert "default to the first sheet" in table_expected["must_not"]
    assert "both candidate sheets" in table_expected["must_preserve"]

    print(f"Validated {len(fixtures)} independent fixtures.")


if __name__ == "__main__":
    main()
