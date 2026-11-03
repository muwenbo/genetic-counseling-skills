#!/usr/bin/env python3
"""Validate and package the plugin as a WorkBuddy open-platform expert (Agent type).

The rules mirror the WorkBuddy open-platform expert specification
(https://open.workbuddy.cn/docs/expert). The platform remains the authority;
this check only catches known rejection causes before upload.
"""

from __future__ import annotations

import argparse
import json
import re
import struct
import sys
import zipfile
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PLUGIN_ROOT = REPOSITORY_ROOT / "plugins/rare-disease-genetic-counseling"
DEFAULT_OUTPUT_DIR = REPOSITORY_ROOT / "dist"

MANIFEST_PATH = ".codebuddy-plugin/plugin.json"
REQUIRED_FIELDS = (
    "name",
    "version",
    "description",
    "author",
    "agents",
    "expertType",
    "agentName",
    "plugin",
    "displayName",
    "profession",
    "displayDescription",
    "avatar",
    "categoryId",
    "defaultInitPrompt",
    "tags",
    "quickPrompts",
)
BILINGUAL_FIELDS = ("displayName", "profession", "displayDescription", "defaultInitPrompt")
CATEGORY_IDS = {
    "01-ProductDesign",
    "02-Engineering",
    "03-GameSpatial",
    "04-DataAI",
    "05-MarketingGrowth",
    "06-ContentCreative",
    "07-SalesCommerce",
    "08-FinanceInvestment",
    "09-OperationsHR",
    "10-ProjectQuality",
    "11-SecurityCompliance",
    "12-IndustryConsultant",
    "13-TencentZone",
    "14-WorldWise",
    "15-Education",
}
ZH_DESCRIPTION_LENGTH = (40, 50)
AVATAR_SIZE = (512, 512)
AVATAR_MAX_BYTES = 500 * 1024
AGENT_REQUIRED_KEYS = ("name", "description", "displayName", "profession")
AGENT_FORBIDDEN_KEYS = ("tools",)
NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SKILL_PATH_PATTERN = re.compile(r"^\./skills/[a-z0-9]+(?:-[a-z0-9]+)*$")
SEMVER_PATTERN =re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$")

# Other platforms' metadata stays out of the expert package so the platform
# parser sees exactly one manifest.
EXCLUDED_NAMES = {".DS_Store", "__pycache__", ".claude-plugin", ".codex-plugin"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}


def _is_bilingual(value: object) -> bool:
    return (
        isinstance(value, dict)
        and isinstance(value.get("en"), str)
        and isinstance(value.get("zh"), str)
        and bool(value["en"].strip())
        and bool(value["zh"].strip())
    )


def _resolve_inside(root: Path, relative: str) -> Path | None:
    candidate = (root / relative).resolve()
    if candidate != root and root not in candidate.parents:
        return None
    return candidate


def _image_size(path: Path) -> tuple[int, int] | None:
    data = path.read_bytes()
    if data.startswith(b"\x89PNG\r\n\x1a\n") and data[12:16] == b"IHDR":
        return struct.unpack(">II", data[16:24])
    if data.startswith(b"\xff\xd8"):
        index = 2
        while index + 9 < len(data):
            if data[index] != 0xFF:
                return None
            marker = data[index + 1]
            length = struct.unpack(">H", data[index + 2 : index + 4])[0]
            if marker in (0xC0, 0xC1, 0xC2):
                height, width = struct.unpack(">HH", data[index + 5 : index + 9])
                return width, height
            index += 2 + length
    return None


def _front_matter_keys(path: Path) -> set[str] | None:
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    keys: set[str] = set()
    for line in lines[1:]:
        if line.strip() == "---":
            return keys
        match = re.match(r"^([A-Za-z_][\w-]*):", line)
        if match:
            keys.add(match.group(1))
    return None


def _front_matter_value(path: Path, key: str) -> str | None:
    for line in path.read_text(encoding="utf-8-sig").splitlines()[1:]:
        if line.strip() == "---":
            return None
        match = re.match(rf"^{re.escape(key)}:\s*(.+)$", line)
        if match:
            return match.group(1).strip().strip("\"'")
    return None


def validate(plugin_root: Path) -> list[str]:
    """Return every rule violation; an empty list means the package is ready."""
    plugin_root = plugin_root.resolve()
    errors: list[str] = []
    manifest_file = plugin_root / MANIFEST_PATH
    if not manifest_file.is_file():
        return [f"missing {MANIFEST_PATH}"]
    try:
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        return [f"{MANIFEST_PATH} is not valid JSON: {error}"]

    extra = sorted(
        item.name for item in manifest_file.parent.iterdir() if item.name != "plugin.json"
    )
    if extra:
        errors.append(f".codebuddy-plugin/ must contain only plugin.json, found {extra}")

    for field in REQUIRED_FIELDS:
        if field not in manifest:
            errors.append(f"missing required field: {field}")
    if errors:
        return errors

    name = manifest["name"]
    if not isinstance(name, str) or not NAME_PATTERN.match(name):
        errors.append("name must be lowercase letters, digits, and hyphens")
    if name != plugin_root.name:
        errors.append(f"name {name!r} must match the plugin directory {plugin_root.name!r}")
    if manifest["plugin"] != name:
        errors.append("plugin must equal name")
    if manifest["expertType"] != "agent":
        errors.append("expertType must be 'agent' for this package")
    if not SEMVER_PATTERN.match(str(manifest["version"])):
        errors.append("version must be semantic (for example 1.0.0)")
    author = manifest["author"]
    if not (isinstance(author, dict) and author.get("name") and author.get("email")):
        errors.append("author must include name and email")

    for field in BILINGUAL_FIELDS:
        if not _is_bilingual(manifest[field]):
            errors.append(f"{field} must be an object with non-empty en and zh strings")
    if _is_bilingual(manifest["displayDescription"]):
        length = len(manifest["displayDescription"]["zh"])
        low, high = ZH_DESCRIPTION_LENGTH
        if not low <= length <= high:
            errors.append(
                f"displayDescription.zh must be {low}-{high} characters, found {length}"
            )

    for field in ("tags", "quickPrompts"):
        items = manifest[field]
        if not isinstance(items, list) or len(items) != 3:
            errors.append(f"{field} must contain exactly 3 items")
        elif not all(_is_bilingual(item) for item in items):
            errors.append(f"every {field} item must have non-empty en and zh strings")
    quick_prompts = manifest["quickPrompts"]
    if isinstance(quick_prompts, list) and quick_prompts:
        if manifest["defaultInitPrompt"] != quick_prompts[0]:
            errors.append("defaultInitPrompt must equal quickPrompts[0]")

    if manifest["categoryId"] not in CATEGORY_IDS:
        errors.append(f"categoryId {manifest['categoryId']!r} is not a platform category")

    avatar = _resolve_inside(plugin_root, manifest["avatar"])
    if avatar is None or not avatar.is_file():
        errors.append(f"avatar file not found: {manifest['avatar']}")
    else:
        if avatar.stat().st_size > AVATAR_MAX_BYTES:
            errors.append("avatar must be at most 500KB")
        size = _image_size(avatar)
        if size is None:
            errors.append("avatar must be a PNG or JPG image")
        elif size != AVATAR_SIZE:
            errors.append(f"avatar must be 512x512 pixels, found {size[0]}x{size[1]}")

    agents = manifest["agents"]
    expected_agent = f"./agents/{manifest['agentName']}.md"
    if not isinstance(agents, list) or expected_agent not in agents:
        errors.append(f"agents must list {expected_agent}")
    for relative in agents if isinstance(agents, list) else []:
        if not relative.startswith("./"):
            errors.append(f"agent path must start with ./: {relative}")
            continue
        agent_file = _resolve_inside(plugin_root, relative)
        if agent_file is None or not agent_file.is_file():
            errors.append(f"agent file not found: {relative}")
            continue
        keys = _front_matter_keys(agent_file)
        if keys is None:
            errors.append(f"{relative} has no YAML front matter")
            continue
        for key in AGENT_REQUIRED_KEYS:
            if key not in keys:
                errors.append(f"{relative} front matter is missing {key}")
        for key in AGENT_FORBIDDEN_KEYS:
            if key in keys:
                errors.append(f"{relative} must not declare {key}; the platform assigns tools")
        if _front_matter_value(agent_file, "name") != agent_file.stem:
            errors.append(f"{relative} front matter name must equal its file name")

    skills = manifest.get("skills", [])
    for index, relative in enumerate(skills):
        if not isinstance(relative, str) or not SKILL_PATH_PATTERN.match(relative):
            errors.append(
                f'skills[{index}] must use the "./skills/<name>" format, found {relative!r}'
            )
            continue
        if not (plugin_root / relative / "SKILL.md").is_file():
            errors.append(f"skill directory lacks SKILL.md: {relative}")
    skills_root = plugin_root / "skills"
    if skills and skills_root.is_dir():
        unlisted = sorted(
            f"./skills/{item.name}"
            for item in skills_root.iterdir()
            if item.is_dir() and f"./skills/{item.name}" not in skills
        )
        if unlisted:
            errors.append(f"skills must list every bundled skill, missing {unlisted}")

    return errors


def _included(path: Path, plugin_root: Path) -> bool:
    parts = path.relative_to(plugin_root).parts
    if any(part in EXCLUDED_NAMES for part in parts):
        return False
    return path.suffix not in EXCLUDED_SUFFIXES


def build(plugin_root: Path, output_dir: Path) -> Path:
    plugin_root = plugin_root.resolve()
    manifest = json.loads((plugin_root / MANIFEST_PATH).read_text(encoding="utf-8"))
    output_dir.mkdir(parents=True, exist_ok=True)
    archive = output_dir / f"{manifest['name']}-{manifest['version']}.zip"
    files = sorted(
        path
        for path in plugin_root.rglob("*")
        if path.is_file() and _included(path, plugin_root)
    )
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
        for path in files:
            bundle.write(path, Path(manifest["name"]) / path.relative_to(plugin_root))
    return archive


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plugin-root", type=Path, default=DEFAULT_PLUGIN_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--check-only", action="store_true", help="validate without writing a zip"
    )
    args = parser.parse_args()

    errors = validate(args.plugin_root)
    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        return 1
    if args.check_only:
        print("WorkBuddy expert package is valid.")
        return 0
    archive = build(args.plugin_root, args.output_dir)
    print(f"Wrote {archive}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
