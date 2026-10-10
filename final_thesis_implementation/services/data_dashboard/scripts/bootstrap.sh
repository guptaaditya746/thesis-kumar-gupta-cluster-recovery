#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$SERVICE_ROOT"

command -v uv >/dev/null 2>&1 || {
  echo "uv is required. Install it from https://docs.astral.sh/uv/" >&2
  exit 1
}

uv sync --all-extras
uv run data-dashboard config-check
uv run data-dashboard catalog build

echo
echo "Dashboard installed. Start it with:"
echo "  cd $SERVICE_ROOT"
echo "  uv run data-dashboard serve"
