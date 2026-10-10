#!/usr/bin/env bash
set -euo pipefail

if [[ "${CONFIRM_WIKIPEDIA_DOWNLOAD:-}" != "YES" ]]; then
  echo "Wikipedia-18 is extremely large."
  echo "Re-run with: CONFIRM_WIKIPEDIA_DOWNLOAD=YES $0"
  exit 2
fi

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
cd "$SCRIPT_DIR/.."
uv run data-prep prepare \
  nq triviaqa bamboogle hotpotqa 2wikimultihopqa musique \
  --include-large
