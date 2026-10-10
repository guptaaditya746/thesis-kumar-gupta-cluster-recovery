#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
cd "$SCRIPT_DIR/.."
uv run data-prep prepare \
  bright_biology \
  bright_earth_science \
  bright_economics \
  bright_robotics
