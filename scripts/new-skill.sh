#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 || $# -gt 3 ]]; then
  echo "usage: scripts/new-skill.sh <plugin-name> <skill-name> [description]" >&2
  exit 2
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RAW_PLUGIN="$1"
RAW_NAME="$2"
DESCRIPTION="${3:-Use this skill for focused, reusable agent work.}"

PLUGIN="$(printf '%s' "$RAW_PLUGIN" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/-/g; s/^-+//; s/-+$//; s/-+/-/g')"
NAME="$(printf '%s' "$RAW_NAME" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/-/g; s/^-+//; s/-+$//; s/-+/-/g')"
if [[ -z "$PLUGIN" ]]; then
  echo "invalid plugin name: $RAW_PLUGIN" >&2
  exit 2
fi
if [[ -z "$NAME" ]]; then
  echo "invalid skill name: $RAW_NAME" >&2
  exit 2
fi

PLUGIN_DIR="$ROOT/plugins/$PLUGIN"
if [[ ! -f "$PLUGIN_DIR/.claude-plugin/plugin.json" ]]; then
  echo "plugin does not exist: $PLUGIN_DIR" >&2
  exit 1
fi

DIR="$PLUGIN_DIR/skills/$NAME"
if [[ -e "$DIR" ]]; then
  echo "skill already exists: $DIR" >&2
  exit 1
fi

mkdir -p "$DIR"
cat > "$DIR/SKILL.md" <<EOF_SKILL
---
name: $NAME
description: $DESCRIPTION
---

# $NAME

$DESCRIPTION

## Workflow

1. Clarify the task from available context.
2. Do the smallest useful work that moves the task forward.
3. Verify the result before handing it back.
EOF_SKILL

echo "created skill: $DIR"
