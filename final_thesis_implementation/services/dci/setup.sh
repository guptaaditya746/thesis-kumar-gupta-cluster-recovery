#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

PI_ROOT="${DCI_PI_ROOT:-$ROOT/../pi_runtime/pi-mono}"
PI_CLI="$PI_ROOT/packages/coding-agent/dist/cli.js"
PI_AGENT_DIR="$PI_ROOT/.pi/agent"

echo "==> Setting up standalone DCI service"

if ! command -v uv >/dev/null 2>&1; then
  echo "ERROR: uv is required but was not found on PATH." >&2
  exit 2
fi

if ! command -v rg >/dev/null 2>&1; then
  echo "WARN: ripgrep (rg) is not installed; DCI direct-corpus runs expect it." >&2
fi

echo "==> Syncing Python dependencies"
uv sync

if ! command -v node >/dev/null 2>&1; then
  echo "ERROR: node is required by Pi." >&2
  exit 2
fi

NODE_MAJOR="$(node --version | sed 's/^v//' | cut -d. -f1)"
if [ "${NODE_MAJOR:-0}" -lt 20 ]; then
  echo "ERROR: Pi requires Node >= 20; found $(node --version)." >&2
  exit 2
fi

if [ ! -f "$PI_CLI" ]; then
  echo "ERROR: Pi CLI is not built at: $PI_CLI" >&2
  echo "       This DCI service intentionally does not vendor or modify Pi." >&2
  echo "       Build your existing services/pi_runtime/pi-mono checkout first," >&2
  echo "       or set DCI_PI_ROOT=/absolute/path/to/pi-mono." >&2
  exit 2
fi

if [ ! -d "$PI_AGENT_DIR" ]; then
  echo "WARN: Pi agent directory does not exist: $PI_AGENT_DIR" >&2
fi

echo "==> DCI service ready"
echo "    Pi root: $PI_ROOT"
echo "    Validate: uv run --no-sync --env-file .env dci-service --config config/single.toml --dry-run"
