#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 || $# -gt 2 ]]; then
  echo "usage: scripts/new-plugin.sh <plugin-name> [description]" >&2
  exit 2
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RAW_NAME="$1"
DESCRIPTION="${2:-Personal agent plugin for cheese-plugins.}"

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

mkdir -p "$PLUGIN_DIR/.codex-plugin" "$PLUGIN_DIR/skills" "$PLUGIN_DIR/commands" "$PLUGIN_DIR/agents"

python3 - "$ROOT" "$NAME" "$DESCRIPTION" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
name = sys.argv[2]
description = sys.argv[3]
plugin_dir = root / "plugins" / name

manifest = {
    "name": name,
    "version": "0.1.0",
    "description": description,
    "author": {"name": "Jianan Liu"},
    "skills": "./skills/",
    "interface": {
        "displayName": " ".join(part.capitalize() for part in name.split("-")),
        "shortDescription": description[:80],
        "longDescription": description,
        "developerName": "Jianan Liu",
        "category": "Productivity",
        "capabilities": [],
        "defaultPrompt": f"Use {name} to help with this task."
    }
}
(plugin_dir / ".codex-plugin" / "plugin.json").write_text(
    json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)

marketplace_path = root / "marketplace.json"
marketplace = json.loads(marketplace_path.read_text(encoding="utf-8"))
plugins = marketplace.setdefault("plugins", [])
plugins.append({
    "name": name,
    "source": {"source": "local", "path": f"./plugins/{name}"},
    "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
    "category": "Productivity"
})
marketplace_path.write_text(json.dumps(marketplace, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY

echo "created plugin: $PLUGIN_DIR"

