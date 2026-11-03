#!/usr/bin/env python3
"""Validate fixture integrity without calling clinical services."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def load(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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

    seq_upstream_input, seq_upstream_expected = loaded[
        "SEQ-002-pinned-upstream-annotation"
    ]
    assert seq_upstream_input["genome_build"] == "hg38"
    assert seq_upstream_input["normalization"]["ref_alt_verified"] is True
    assert seq_upstream_expected["adapter_operation"] == "annotate"
    assert seq_upstream_expected["upstream_commit"] == (
        "05bf1f6bce4e6be04f9e52b55db1d5fee03029d9"
    )
    assert "run upstream classify_variant.py" in seq_upstream_expected["must_not"]

    seq_tally_input, seq_tally_expected = loaded["SEQ-003-acmg-evidence-point-tally"]
    assert seq_tally_input["request"] == "classify_sequence_variant"
    assert seq_tally_expected["criterion_table_required"] is True
    assert seq_tally_expected["criterion_fields"] == [
        "criterion",
        "state",
        "original_strength",
        "effective_strength",
        "points",
        "evidence",
        "rationale",
        "limitations_or_missing_confirmation",
        "confirmation_status",
    ]
    assert seq_tally_expected["required_totals"] == [
        "pathogenic_subtotal",
        "benign_subtotal",
        "signed_total",
    ]
    assert seq_tally_expected["default_scoring_framework"] == {
        "name": "Bayesian ACMG/AMP point calibration",
        "version": "Tavtigian et al. 2020",
        "pmid": "32720330",
        "doi": "10.1002/humu.24088",
    }
    thresholds = seq_tally_expected["bayesian_acmg_amp_thresholds"]
    assert thresholds["Pathogenic"] == ">=10"
    assert thresholds["Likely pathogenic"] == "6-9"
    assert thresholds["Uncertain significance"] == "0-5"
    assert thresholds["Likely benign"] == "-1 to -6"
    assert thresholds["Benign"] == "<=-7"
    assert "double count correlated evidence" in seq_tally_expected["must_not"]

    legacy_input, legacy_expected = loaded["SEQ-004-legacy-transcript-mapping"]
    assert legacy_input["variant"] == "NM_004006.2:c.6787del"
    assert legacy_expected["mapping_chain"] == [
        "contextual_spdi",
        "canonical_genomic_spdi",
        "canonical_genomic_hgvs",
        "vep_annotation",
    ]
    assert legacy_expected["preserve_asserted_transcript"] is True
    assert legacy_expected["fallback_trigger"] == (
        "explicit_ensembl_unresolved_variant_response"
    )
    assert legacy_expected["require_chromosome_accession_concordance"] is True
    assert legacy_expected["unreconciled_insertions"] == "blocked"
    assert legacy_expected["service_failures_do_not_trigger_fallback"] is True
    assert legacy_expected["preserve_prior_remote_disclosures_on_later_failure"] is True
    assert "replace .2 with .3 by string substitution" in legacy_expected["must_not"]
    assert (
        "infer equivalence from matching c. coordinates" in legacy_expected["must_not"]
    )

    grch37_input, grch37_expected = loaded["SEQ-005-grch37-ensembl-routing"]
    assert grch37_input["genome_build"] == "hg19"
    assert grch37_expected["endpoint"] == "https://grch37.rest.ensembl.org"
    assert grch37_expected["returned_assembly_required"] == "GRCh37"
    assert grch37_expected["independent_ref_verification_operation"] == (
        "GET /sequence/region/human/{region}"
    )
    assert grch37_expected["implicit_liftover"] is False
    assert (
        "send GRCh37 coordinates to the GRCh38 endpoint" in grch37_expected["must_not"]
    )

    lift_input, lift_expected = loaded["SEQ-006-bidirectional-liftover"]
    assert lift_input["from_build"] == "hg19"
    assert lift_input["to_build"] == "hg38"
    assert lift_expected["required_validation"] == [
        "source_ref_verified",
        "single_contiguous_mapping",
        "target_ref_verified",
        "roundtrip_concordant",
    ]
    assert (
        "return coordinate-only mapping as a verified allele"
        in lift_expected["must_not"]
    )

    setup_input, setup_expected = loaded[
        "SEQ-007-approved-pinned-dependency-setup"
    ]
    assert setup_input["dependency_status"] == "upstream_dependency_unavailable"
    assert setup_input["user_approved_network_install"] is False
    assert setup_expected["outcome_before_approval"] == "blocked"
    assert setup_expected["approved_setup_operation"] == (
        "prepare --allow-network-install"
    )
    assert setup_expected["required_verification"] == [
        "exact_git_commit",
        "required_resource_layout",
        "mit_license",
    ]
    assert setup_expected["setup_disclosed_fields"] == ["repository", "commit"]
    assert setup_expected["clinical_data_disclosed"] is False
    assert setup_expected["existing_invalid_target_behavior"] == "do_not_overwrite"
    assert setup_expected["failure_semantics"] == "capability_unavailable"
    assert "download before explicit approval" in setup_expected["must_not"]
    assert "fetch a moving branch" in setup_expected["must_not"]
    assert (
        "send a variant or case fact during setup" in setup_expected["must_not"]
    )

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

    recall_input, recall_expected = loaded["TABLE-002-safety-recall-union"]
    assert recall_input["phenotype_graph"]["returned_gene_symbols"] == ["GENE_B"]
    assert recall_expected["candidate_set_operation"] == "union"
    assert recall_expected["phenotype_rank_may_reorder_only"] is True
    assert recall_expected["required_safety_recall"]["record_1"] == [
        "database_pathogenic_assertion",
        "severe_consequence",
    ]
    assert recall_expected["unknown_frequency"]["retain_for_review"] is True
    assert recall_expected["unknown_frequency"]["rarity_established"] is False
    assert (
        "filter reviewed variants by phenotype graph top-k"
        in recall_expected["must_not"]
    )

    callset_input, callset_expected = loaded["CALLSET-001-missing-build"]
    assert callset_input["genome_build"] is None
    assert callset_input["external_prioritization_result"] is None
    assert callset_expected["outcome"] == "blocked"
    assert "genome_build_missing" in callset_expected["blocking_reasons"]
    assert "assume a genome build" in callset_expected["must_not"]
    assert (
        "treat an unannotated variant as rare by default"
        in callset_expected["must_not"]
    )
    assert (
        "run automatically as a fallback from disease ranking"
        in callset_expected["must_not"]
    )

    hpo_review_input, hpo_review_expected = loaded[
        "HPO-001-chinese-translation-review-required"
    ]
    assert hpo_review_input["source_language"] == "zh"
    assert hpo_review_input["translation_status"] == "review_required"
    assert len(hpo_review_input["candidate_english_phrases"]) == 2
    assert hpo_review_expected["outcome"] == "blocked_before_remote_retrieval"
    assert hpo_review_expected["hpo_search_request"] is None
    assert hpo_review_expected["base_url"] == "https://rdkg.viknox.com.cn"
    assert (
        "send the Chinese source phrase to /hpo/search"
        in hpo_review_expected["must_not"]
    )

    hpo_verified_input, hpo_verified_expected = loaded[
        "HPO-002-chinese-translation-agent-verified"
    ]
    assert hpo_verified_input["translation_status"] == "agent_verified"
    assert hpo_verified_expected["outcome"] == "ready_for_hpo_search"
    assert hpo_verified_expected["retrieval_mode"] == "sapbert_vector_search"
    assert hpo_verified_expected["request_body"]["queries"] == ["short stature"]
    assert hpo_verified_expected["endpoint"] == "POST /hpo/search"
    assert "身材矮小" not in json.dumps(
        hpo_verified_expected["request_body"], ensure_ascii=False
    )

    pedigree_input, pedigree_expected = loaded["PED-001-file-url-blocked"]
    assert pedigree_input["browser"]["file_url_allowed"] is False
    assert pedigree_input["browser"]["loopback_http_allowed"] is True
    assert pedigree_expected["outcome"] == "ready_for_loopback_rendering"
    assert pedigree_expected["navigation_scheme"] == "http"
    assert pedigree_expected["bind_host"] == "127.0.0.1"
    assert pedigree_expected["served_content"] == ["bundled_pedigree_chart_html"]
    assert pedigree_expected["family_data_transport"] == "browser_file_upload"
    assert "navigate to a file URL" in pedigree_expected["must_not"]
    assert (
        pedigree_expected["fallback_if_loopback_fails"]
        == "return_validated_json_and_report_figure_not_generated"
    )

    svg_input, svg_expected = loaded["PED-002-standalone-svg-editable-tab"]
    assert svg_input["requested_outputs"] == ["json", "svg", "editable_tab"]
    assert svg_expected["svg_export"]["raw_outer_html_allowed"] is False
    assert svg_expected["svg_export"]["required_root_attributes"] == [
        "xmlns",
        "width",
        "height",
        "viewBox",
    ]
    assert svg_expected["svg_export"]["background"] == "white"
    assert svg_expected["editor_tab"]["preserve_as_deliverable"] is True
    assert svg_expected["editor_tab"]["close_after_export"] is False
    assert svg_expected["loopback_server"]["stop_after_page_loaded"] is True

    family_input, family_expected = loaded["PED-003-nuclear-family-import-verification"]
    family_ids = [item["id"] for item in family_input["family"]["individuals"]]
    assert family_ids == ["father", "mother", "proband", "sister", "brother"]
    assert family_input["browser"]["download_event_observable"] is False
    generated = family_expected["generated_json"]
    assert "genotypes" in generated["required_keys_per_individual"]
    assert generated["empty_genotypes_value"] == {}
    assert generated["proband_count"] == 1
    assert generated["deceased_ids"] == ["brother"]
    assert generated["affected_ids"] == ["proband", "brother"]
    assert family_expected["import"]["supported_paths"] == [
        "visible_open_button_with_prearmed_filechooser",
        "direct_file_input_upload_without_click",
    ]
    assert family_expected["import"]["hidden_input_click_allowed"] is False
    assert family_expected["import"]["file_chooser_wait_armed_before_click"] is True
    family_svg = family_expected["svg_export"]
    assert family_svg["path"] == "read_markup_and_build_outside_page"
    assert family_svg["clone_node_in_page_evaluation"] is False
    assert family_svg["repeat_export_clicks_allowed"] is False
    assert family_svg["export_excluded_nodes_present"] == 0
    assert family_svg["required_root_attributes"] == [
        "xmlns",
        "width",
        "height",
        "viewBox",
    ]
    assert "omit genotypes from a generated individual" in family_expected["must_not"]
    assert (
        "describe a screenshot as an exported SVG or PNG" in family_expected["must_not"]
    )

    package_input, package_expected = loaded["PACKAGE-001-gui-installation"]
    assert package_input["surfaces"] == ["general_gui_agent"]
    repository_root = ROOT.parent
    for relative_path in package_expected["required_manifests"]:
        assert (repository_root / relative_path).is_file(), (
            f"missing GUI packaging manifest: {relative_path}"
        )
    codex_manifest = load(
        repository_root
        / "plugins/rare-disease-genetic-counseling/.codex-plugin/plugin.json"
    )
    claude_manifest = load(
        repository_root
        / "plugins/rare-disease-genetic-counseling/.claude-plugin/plugin.json"
    )
    claude_marketplace = load(repository_root / ".claude-plugin/marketplace.json")
    assert codex_manifest["name"] == package_expected["plugin_name"]
    assert claude_manifest["name"] == package_expected["plugin_name"]
    assert claude_marketplace["plugins"][0]["source"] == (
        package_expected["claude_marketplace_source"]
    )
    documentation = package_expected["documentation"]
    assert documentation["installation_style"] == "agent-directed"
    english_readme = repository_root / documentation["english"]
    chinese_readme = repository_root / documentation["simplified_chinese"]
    assert english_readme.is_file()
    assert chinese_readme.is_file()
    english_text = english_readme.read_text(encoding="utf-8")
    chinese_text = chinese_readme.read_text(encoding="utf-8")
    assert "README.zh-CN.md" in english_text
    assert "README.md" in chinese_text
    assert "https://github.com/muwenbo/genetic-counseling-skills" in english_text
    assert "https://github.com/muwenbo/genetic-counseling-skills" in chinese_text
    assert "Customize → Plugins" not in english_text
    assert "Customize → Plugins" not in chinese_text
    assert (
        "claim Claude compatibility without a Claude marketplace manifest"
        in package_expected["must_not"]
    )

    _expert_input, expert_expected = loaded["PACKAGE-002-workbuddy-expert"]
    packager = _load_module(
        "package_workbuddy_expert",
        repository_root / expert_expected["packaging_script"],
    )
    plugin_root = repository_root / "plugins" / expert_expected["plugin_name"]
    assert packager.validate(plugin_root) == expert_expected["validation_errors"]
    expert_manifest = load(repository_root / expert_expected["manifest"])
    assert expert_manifest["name"] == expert_expected["plugin_name"]
    assert expert_manifest["agentName"] == expert_expected["agent_name"]
    assert expert_expected["skill_path_format"] == "./skills/<name>"
    assert set(expert_expected["archive_excludes"]) <= packager.EXCLUDED_NAMES
    agent_text = (
        plugin_root / "agents" / f"{expert_expected['agent_name']}.md"
    ).read_text(encoding="utf-8")
    for phrase in expert_expected["agent_prompt_must_state"]:
        assert phrase in agent_text, f"agent prompt must state: {phrase}"
    skill_names = sorted(
        path.name for path in (plugin_root / "skills").iterdir() if path.is_dir()
    )
    for skill_name in skill_names:
        assert f"`{skill_name}`" in agent_text, f"agent prompt must route to {skill_name}"
    assert expert_expected["skills_list_every_bundled_skill"] is True
    assert expert_manifest["skills"] == [f"./skills/{name}" for name in skill_names]
    assert (
        "declare tools in the agent front matter" in expert_expected["must_not"]
    )

    print(f"Validated {len(fixtures)} independent fixtures.")


if __name__ == "__main__":
    main()
