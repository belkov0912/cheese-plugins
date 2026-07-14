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
    i = 1
    while i < len(lines):
        line = lines[i]
        if line.strip() == "---":
            return data
        match = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if match:
            key, value = match.group(1), match.group(2).strip()
            if re.fullmatch(r"[>|][+-]?", value):
                folded = value.startswith(">")
                block = []
                i += 1
                while i < len(lines) and (not lines[i] or lines[i][0].isspace()):
                    block.append(lines[i].strip())
                    i += 1
                parts = [part for part in block if part]
                data[key] = (" " if folded else "\n").join(parts)
                continue
            data[key] = value.strip('"').strip("'")
        i += 1
    fail(f"{path.relative_to(root)} frontmatter is not closed")
    return data

def has_bad_placeholder(path: Path) -> bool:
    text = path.read_text(encoding="utf-8", errors="ignore")
    return bool(re.search(r"TODO|TBD|FIXME|placeholder|example\.com|\[TODO:", text, re.I))

# --- marketplace index (Claude Code / codex shared format) ---
marketplace_path = root / ".claude-plugin" / "marketplace.json"
if not marketplace_path.exists():
    fail(".claude-plugin/marketplace.json is missing")
    marketplace = None
else:
    marketplace = load_json(marketplace_path)

registered_plugin_dirs = set()
if marketplace:
    if not marketplace.get("name"):
        fail(".claude-plugin/marketplace.json missing name")
    if not isinstance(marketplace.get("plugins"), list):
        fail(".claude-plugin/marketplace.json plugins must be a list")
    for entry in marketplace.get("plugins", []):
        name = entry.get("name")
        source = entry.get("source")
        if not name:
            fail("marketplace entry missing name")
            continue
        if not isinstance(source, str) or not source:
            fail(f"marketplace entry {name} must have a string source path")
            continue
        if not entry.get("description"):
            fail(f"marketplace entry {name} missing description")
        if not entry.get("category"):
            fail(f"marketplace entry {name} missing category")
        plugin_dir = (root / source).resolve()
        registered_plugin_dirs.add(plugin_dir)
        try:
            plugin_dir.relative_to(root.resolve())
        except ValueError:
            fail(f"marketplace entry {name} points outside repo: {source}")
            continue
        if not plugin_dir.exists():
            fail(f"marketplace entry {name} path does not exist: {source}")
            continue
        plugin_json = plugin_dir / ".claude-plugin" / "plugin.json"
        if not plugin_json.exists():
            fail(f"marketplace entry {name} missing plugin manifest: {plugin_json.relative_to(root)}")
        else:
            manifest = load_json(plugin_json)
            if manifest and manifest.get("name") != name:
                fail(f"marketplace entry {name} does not match {plugin_json.relative_to(root)} name")

# --- every plugin dir is registered ---
for plugin_dir in sorted((root / "plugins").iterdir() if (root / "plugins").exists() else []):
    if not plugin_dir.is_dir() or plugin_dir.name.startswith("_"):
        continue
    if plugin_dir.resolve() not in registered_plugin_dirs:
        fail(f"plugins/{plugin_dir.name} is not registered in .claude-plugin/marketplace.json")

if (root / "skills").exists():
    fail("top-level skills/ is not used; put skills under plugins/<plugin>/skills/")

# --- plugin manifests ---
plugin_versions = {}
for plugin_json in sorted((root / "plugins").glob("*/.claude-plugin/plugin.json")):
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
    if has_bad_placeholder(plugin_json):
        fail(f"{plugin_json.relative_to(root)} contains placeholder-like text")
    if manifest.get("version"):
        plugin_versions[plugin_dir.name] = manifest["version"]

# all plugins share one version — bump them together
if len(set(plugin_versions.values())) > 1:
    fail(f"plugins must all share one version, found: {plugin_versions}")

# --- skills ---
skill_files = sorted((root / "plugins").glob("*/skills/*/SKILL.md"))
for skill_file in skill_files:
    data = frontmatter(skill_file)
    if not data.get("name"):
        fail(f"{skill_file.relative_to(root)} missing frontmatter name")
    if not data.get("description"):
        fail(f"{skill_file.relative_to(root)} missing frontmatter description")
    if data.get("name") and data["name"] != skill_file.parent.name:
        fail(f"{skill_file.relative_to(root)} name does not match folder")
    if data.get("name") and not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", data["name"]):
        fail(f"{skill_file.relative_to(root)} name must use lowercase letters, numbers, and hyphens")
    if len(data.get("name", "")) > 64:
        fail(f"{skill_file.relative_to(root)} name exceeds 64 characters")
    if len(data.get("description", "")) > 1024:
        fail(f"{skill_file.relative_to(root)} description exceeds 1024 characters")

# Current rule docs state only the active contract; migration history belongs in archives.
# 「当日此前」is intraday metric wording (earlier the same day), not migration history.
migration_terms = re.compile(r"旧版|新版|原来|(?<!当日)此前|不再|改为|当前版|本轮|初版|新口径|旧\s*AI")
stock_selection_rules = root / "plugins" / "stock-selection-rules"
current_rule_docs = [stock_selection_rules / "README.md"]
current_rule_docs += sorted((stock_selection_rules / "docs").glob("*.md"))
current_rule_docs += sorted((stock_selection_rules / "skills").glob("*/SKILL.md"))
for path in current_rule_docs:
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if migration_terms.search(line):
            fail(f"{path.relative_to(root)}:{line_number} contains migration history; state the current rule directly")

if errors:
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    sys.exit(1)

print("cheese-plugins validation passed")
PY
