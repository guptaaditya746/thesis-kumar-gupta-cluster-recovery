#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
config_path="${1:-config/smoke/qa-2wikimultihopqa.toml}"
uv run query-driven --config "$config_path"
