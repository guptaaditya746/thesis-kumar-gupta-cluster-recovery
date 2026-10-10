#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required: https://docs.astral.sh/uv/" >&2
  exit 1
fi

uv sync

echo
echo "Core service installed."
echo "For CLIP/Gemini/image features, run: uv sync --extra multimodal"
echo "Smoke test: ./scripts/run.sh"
echo "Full runs: choose a config under config/bright, config/qa, or config/reproduction"
