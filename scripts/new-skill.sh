#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 || $# -gt 2 ]]; then
  echo "usage: scripts/new-skill.sh <skill-name> [description]" >&2
  exit 2
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RAW_NAME="$1"
DESCRIPTION="${2:-Use this skill for focused, reusable agent work.}"

NAME="$(printf '%s' "$RAW_NAME" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/-/g; s/^-+//; s/-+$//; s/-+/-/g')"
if [[ -z "$NAME" ]]; then
  echo "invalid skill name: $RAW_NAME" >&2
  exit 2
fi

DIR="$ROOT/skills/$NAME"
if [[ -e "$DIR" ]]; then
  echo "skill already exists: $DIR" >&2
  exit 1
fi

SHORT_DESCRIPTION="$DESCRIPTION"
if [[ ${#SHORT_DESCRIPTION} -lt 25 ]]; then
  SHORT_DESCRIPTION="$DESCRIPTION for reusable agent work"
fi
if [[ ${#SHORT_DESCRIPTION} -gt 64 ]]; then
  SHORT_DESCRIPTION="${SHORT_DESCRIPTION:0:64}"
fi

mkdir -p "$DIR/agents"
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

cat > "$DIR/agents/openai.yaml" <<EOF_OPENAI
interface:
  display_name: "$NAME"
  short_description: "$SHORT_DESCRIPTION"
  default_prompt: "Use \$$NAME to help with this task:"
EOF_OPENAI

echo "created skill: $DIR"
