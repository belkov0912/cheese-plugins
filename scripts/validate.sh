#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

python3 - "$ROOT" <<'PY'
import json
import re
import sys
from pathlib import Path

root = Path(sys.argv[1])
errors = []

def fail(message: str) -> None:
    errors.append(message)

def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"{path.relative_to(root)} is not valid JSON: {exc}")
        return None

def frontmatter(path: Path):
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        fail(f"{path.relative_to(root)} missing YAML frontmatter")
        return {}
    data = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return data
        match = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if match:
            value = match.group(2).strip().strip('"').strip("'")
            data[match.group(1)] = value
    fail(f"{path.relative_to(root)} frontmatter is not closed")
    return data

def has_bad_placeholder(path: Path) -> bool:
    text = path.read_text(encoding="utf-8", errors="ignore")
    return bool(re.search(r"TODO|TBD|FIXME|placeholder|example\.com|\[TODO:", text, re.I))

marketplace_path = root / "marketplace.json"
if not marketplace_path.exists():
    fail("marketplace.json is missing")
    marketplace = None
else:
    marketplace = load_json(marketplace_path)

if marketplace:
    if not marketplace.get("name"):
        fail("marketplace.json missing name")
    if not isinstance(marketplace.get("plugins"), list):
        fail("marketplace.json plugins must be a list")
    for entry in marketplace.get("plugins", []):
        name = entry.get("name")
        source = entry.get("source") or {}
        policy = entry.get("policy") or {}
        if not name:
            fail("marketplace entry missing name")
            continue
        if source.get("source") != "local":
            fail(f"marketplace entry {name} must use local source")
        rel_path = source.get("path")
        if not rel_path:
            fail(f"marketplace entry {name} missing source.path")
            continue
        plugin_dir = (root / rel_path).resolve()
        try:
            plugin_dir.relative_to(root.resolve())
        except ValueError:
            fail(f"marketplace entry {name} points outside repo: {rel_path}")
            continue
        if not plugin_dir.exists():
            fail(f"marketplace entry {name} path does not exist: {rel_path}")
        if policy.get("installation") not in {"AVAILABLE", "INSTALLED_BY_DEFAULT", "NOT_AVAILABLE"}:
            fail(f"marketplace entry {name} has invalid policy.installation")
        if policy.get("authentication") not in {"ON_INSTALL", "ON_USE"}:
            fail(f"marketplace entry {name} has invalid policy.authentication")
        if not entry.get("category"):
            fail(f"marketplace entry {name} missing category")

for plugin_json in sorted((root / "plugins").glob("*/.codex-plugin/plugin.json")):
    plugin_dir = plugin_json.parents[1]
    manifest = load_json(plugin_json)
    if not manifest:
        continue
    if manifest.get("name") != plugin_dir.name:
        fail(f"{plugin_json.relative_to(root)} name does not match folder {plugin_dir.name}")
    if not manifest.get("version"):
        fail(f"{plugin_json.relative_to(root)} missing version")
    if not manifest.get("description"):
        fail(f"{plugin_json.relative_to(root)} missing description")
    if not (manifest.get("author") or {}).get("name"):
        fail(f"{plugin_json.relative_to(root)} missing author.name")
    interface = manifest.get("interface") or {}
    for key in ["displayName", "shortDescription", "longDescription", "developerName", "category"]:
        if not interface.get(key):
            fail(f"{plugin_json.relative_to(root)} missing interface.{key}")
    if has_bad_placeholder(plugin_json):
        fail(f"{plugin_json.relative_to(root)} contains placeholder-like text")
    skills_path = manifest.get("skills")
    if skills_path:
        skill_root = (plugin_dir / skills_path).resolve()
        if not skill_root.exists():
            fail(f"{plugin_json.relative_to(root)} skills path does not exist")

skill_files = sorted((root / "skills").glob("*/SKILL.md"))
skill_files += sorted((root / "plugins").glob("*/skills/*/SKILL.md"))
for skill_file in skill_files:
    data = frontmatter(skill_file)
    if not data.get("name"):
        fail(f"{skill_file.relative_to(root)} missing frontmatter name")
    if not data.get("description"):
        fail(f"{skill_file.relative_to(root)} missing frontmatter description")
    if data.get("name") and data["name"] != skill_file.parent.name:
        fail(f"{skill_file.relative_to(root)} name does not match folder")
    openai_yaml = skill_file.parent / "agents" / "openai.yaml"
    if openai_yaml.exists():
        text = openai_yaml.read_text(encoding="utf-8")
        for key in ["display_name", "short_description", "default_prompt"]:
            if key not in text:
                fail(f"{openai_yaml.relative_to(root)} missing {key}")

if errors:
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    sys.exit(1)

print("cheese-plugins validation passed")
PY

