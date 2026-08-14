#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: scripts/bump.sh <version>   (e.g. scripts/bump.sh 1.2.0)" >&2
  exit 2
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="$1"

if [[ ! "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+([.-][0-9A-Za-z.-]+)?$ ]]; then
  echo "invalid version: $VERSION (expected like 1.2.0)" >&2
  exit 2
fi

# All plugins share one version — set every Claude and optional Codex manifest.
python3 - "$ROOT" "$VERSION" <<'PY'
import json, sys
from pathlib import Path

root = Path(sys.argv[1])
version = sys.argv[2]
plugin_jsons = list(root.glob("plugins/*/.claude-plugin/plugin.json"))
plugin_jsons += list(root.glob("plugins/*/.codex-plugin/plugin.json"))
for plugin_json in sorted(plugin_jsons):
    data = json.loads(plugin_json.read_text(encoding="utf-8"))
    old = data.get("version")
    data["version"] = version
    plugin_json.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest_kind = plugin_json.parent.name
    print(f"  {data['name']:<20} {manifest_kind:<15} {old} -> {version}")
PY

echo "set all plugins to $VERSION"
