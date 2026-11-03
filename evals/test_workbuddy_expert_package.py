#!/usr/bin/env python3
"""Focused tests for the WorkBuddy expert-package validator and archive builder."""

from __future__ import annotations

import importlib.util
import json
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = ROOT / "plugins/rare-disease-genetic-counseling"
SCRIPT = ROOT / "scripts/package_workbuddy_expert.py"

spec = importlib.util.spec_from_file_location("package_workbuddy_expert", SCRIPT)
packager = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packager)


class WorkBuddyExpertPackageTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.plugin = Path(self.temp.name) / PLUGIN_ROOT.name
        shutil.copytree(
            PLUGIN_ROOT,
            self.plugin,
            ignore=shutil.ignore_patterns(".DS_Store", "__pycache__"),
        )
        self.manifest_path = self.plugin / packager.MANIFEST_PATH

    def tearDown(self) -> None:
        self.temp.cleanup()

    def edit_manifest(self, **changes: object) -> None:
        manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        manifest.update(changes)
        self.manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
        )

    def test_repository_package_is_valid(self) -> None:
        self.assertEqual(packager.validate(self.plugin), [])

    def test_missing_manifest_is_reported(self) -> None:
        self.manifest_path.unlink()
        self.assertEqual(packager.validate(self.plugin), ["missing .codebuddy-plugin/plugin.json"])

    def test_tag_and_prompt_counts_are_enforced(self) -> None:
        manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        self.edit_manifest(
            tags=manifest["tags"][:2],
            quickPrompts=manifest["quickPrompts"] + [manifest["quickPrompts"][0]],
        )
        errors = packager.validate(self.plugin)
        self.assertIn("tags must contain exactly 3 items", errors)
        self.assertIn("quickPrompts must contain exactly 3 items", errors)

    def test_default_prompt_must_match_first_quick_prompt(self) -> None:
        self.edit_manifest(defaultInitPrompt={"en": "Other", "zh": "其他"})
        self.assertIn(
            "defaultInitPrompt must equal quickPrompts[0]", packager.validate(self.plugin)
        )

    def test_chinese_description_length_is_enforced(self) -> None:
        self.edit_manifest(displayDescription={"en": "Short", "zh": "罕见病遗传咨询"})
        errors = packager.validate(self.plugin)
        self.assertTrue(any(error.startswith("displayDescription.zh") for error in errors))

    def test_unknown_category_and_mismatched_plugin_are_rejected(self) -> None:
        self.edit_manifest(categoryId="16-Healthcare", plugin="other-name")
        errors = packager.validate(self.plugin)
        self.assertIn("plugin must equal name", errors)
        self.assertTrue(any("categoryId" in error for error in errors))

    def test_skills_parent_directory_is_rejected(self) -> None:
        self.edit_manifest(skills=["./skills/"])
        self.assertIn(
            'skills[0] must use the "./skills/<name>" format, found \'./skills/\'',
            packager.validate(self.plugin),
        )

    def test_every_bundled_skill_must_be_listed(self) -> None:
        manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        self.edit_manifest(skills=manifest["skills"][1:])
        errors = packager.validate(self.plugin)
        self.assertTrue(
            any("missing ['./skills/classify-cnv']" in error for error in errors), errors
        )

    def test_agent_tools_declaration_is_rejected(self) -> None:
        agent = self.plugin / "agents/rare-disease-genetic-counselor.md"
        text = agent.read_text(encoding="utf-8")
        agent.write_text(text.replace("maxTurns: 100", "maxTurns: 100\ntools: Bash"), encoding="utf-8")
        errors = packager.validate(self.plugin)
        self.assertTrue(any("must not declare tools" in error for error in errors))

    def test_wrong_avatar_size_is_rejected(self) -> None:
        avatar = self.plugin / "avatars/expert.png"
        data = bytearray(avatar.read_bytes())
        data[16:24] = (256).to_bytes(4, "big") * 2
        avatar.write_bytes(bytes(data))
        self.assertIn(
            "avatar must be 512x512 pixels, found 256x256", packager.validate(self.plugin)
        )

    def test_extra_file_in_manifest_directory_is_rejected(self) -> None:
        (self.plugin / ".codebuddy-plugin/marketplace.json").write_text("{}", encoding="utf-8")
        errors = packager.validate(self.plugin)
        self.assertTrue(any("must contain only plugin.json" in error for error in errors))

    def test_archive_has_single_root_and_excludes_other_manifests(self) -> None:
        (self.plugin / "skills/classify-cnv/__pycache__").mkdir(exist_ok=True)
        (self.plugin / "skills/classify-cnv/__pycache__/x.pyc").write_bytes(b"")
        archive = packager.build(self.plugin, Path(self.temp.name) / "dist")
        with zipfile.ZipFile(archive) as bundle:
            names = bundle.namelist()
        self.assertEqual({name.split("/")[0] for name in names}, {PLUGIN_ROOT.name})
        self.assertIn(f"{PLUGIN_ROOT.name}/.codebuddy-plugin/plugin.json", names)
        self.assertIn(f"{PLUGIN_ROOT.name}/agents/rare-disease-genetic-counselor.md", names)
        for excluded in (".claude-plugin", ".codex-plugin", "__pycache__", ".DS_Store"):
            self.assertFalse(any(f"/{excluded}" in name for name in names), excluded)


if __name__ == "__main__":
    unittest.main()
