#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ "${1:-}" == "--trade-snapshot" ]]; then
  shift
  target="${SCRIPT_DIR}/trade_snapshot.py"
else
  target="${SCRIPT_DIR}/trade_context.py"
fi

declare -a candidates=()
if [[ -n "${R0_REVIEW_PYTHON:-}" ]]; then
  candidates+=("${R0_REVIEW_PYTHON}")
fi
candidates+=("python3" "/usr/bin/python3")

for python_bin in "${candidates[@]}"; do
  if ! command -v "${python_bin}" >/dev/null 2>&1; then
    continue
  fi
  if "${python_bin}" - <<'PY' >/dev/null 2>&1
import pandas  # noqa: F401
import pyarrow  # noqa: F401
PY
  then
    exec "${python_bin}" "${target}" "$@"
  fi
done

echo "找不到同时具备 pandas 和 pyarrow 的 Python。可设置 R0_REVIEW_PYTHON，例如：R0_REVIEW_PYTHON=/usr/bin/python3" >&2
exit 1
