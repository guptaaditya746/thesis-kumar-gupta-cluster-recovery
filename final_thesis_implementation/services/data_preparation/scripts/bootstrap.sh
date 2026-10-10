#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
SERVICE_ROOT=$(cd -- "$SCRIPT_DIR/.." && pwd)
cd "$SERVICE_ROOT"

uv sync --all-groups
uv run data-prep init
uv run data-prep doctor

echo
echo "Bootstrap complete. Try: uv run data-prep catalog"
