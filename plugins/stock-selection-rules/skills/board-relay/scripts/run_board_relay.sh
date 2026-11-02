#!/usr/bin/env bash
# 找一个装好 akshare + pandas + requests 的 Python 来跑 board_relay.py（参数原样透传）。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
target="${SCRIPT_DIR}/board_relay.py"

declare -a candidates=()
[[ -n "${BOARD_RELAY_PYTHON:-}" ]] && candidates+=("${BOARD_RELAY_PYTHON}")
[[ -n "${R0_REVIEW_PYTHON:-}" ]] && candidates+=("${R0_REVIEW_PYTHON}")
candidates+=("python3" "/usr/bin/python3")

for python_bin in "${candidates[@]}"; do
  command -v "${python_bin}" >/dev/null 2>&1 || continue
  if "${python_bin}" -c "import akshare, pandas, requests" >/dev/null 2>&1; then
    exec "${python_bin}" "${target}" "$@"
  fi
done

echo "找不到装好 akshare/pandas/requests 的 Python。先装：python3 -m pip install akshare pandas requests；" \
     "或设置 BOARD_RELAY_PYTHON=/path/to/python3" >&2
exit 1
