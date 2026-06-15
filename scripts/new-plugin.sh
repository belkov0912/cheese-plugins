#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 || $# -gt 3 ]]; then
  echo "usage: scripts/new-plugin.sh <plugin-name> [description] [category]" >&2
  exit 2
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RAW_NAME="$1"
DESCRIPTION="${2:-Personal agent plugin for cheese-plugins.}"
CATEGORY="${3:-general}"

NAME="$(printf '%s' "$RAW_NAME" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/-/g; s/^-+//; s/-+$//; s/-+/-/g')"
if [[ -z "$NAME" ]]; then
  echo "invalid plugin name: $RAW_NAME" >&2
  exit 2
fi

PLUGIN_DIR="$ROOT/plugins/$NAME"
if [[ -e "$PLUGIN_DIR" ]]; then
  echo "plugin already exists: $PLUGIN_DIR" >&2
  exit 1
fi

python3 - "$ROOT" "$NAME" "$DESCRIPTION" "$CATEGORY" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
name = sys.argv[2]
description = sys.argv[3]
category = sys.argv[4]
plugin_dir = root / "plugins" / name
marketplace_path = root / ".claude-plugin" / "marketplace.json"

if marketplace_path.exists():
    marketplace = json.loads(marketplace_path.read_text(encoding="utf-8"))
else:
    marketplace = {
        "name": "cheese-plugins",
        "owner": {"name": "Jianan Liu"},
        "description": "Personal agent plugin workspace.",
        "plugins": [],
    }

plugins = marketplace.setdefault("plugins", [])
if any(entry.get("name") == name for entry in plugins):
    raise SystemExit(f"marketplace entry already exists: {name}")

# Plugin bundle: only skills/ by default. Add commands/ or agents/ when needed.
(plugin_dir / ".claude-plugin").mkdir(parents=True)
(plugin_dir / "skills").mkdir()

display_name = " ".join(part.capitalize() for part in name.split("-"))
manifest = {
    "name": name,
    "version": "0.1.0",
    "description": description,
    "author": {"name": "Jianan Liu"},
    "keywords": [],
}
(plugin_dir / ".claude-plugin" / "plugin.json").write_text(
    json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)

plugins.append({
    "name": name,
    "displayName": display_name,
    "source": f"./plugins/{name}",
    "description": description,
    "category": category,
})
marketplace_path.parent.mkdir(parents=True, exist_ok=True)
marketplace_path.write_text(json.dumps(marketplace, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY

echo "created plugin: $PLUGIN_DIR"
