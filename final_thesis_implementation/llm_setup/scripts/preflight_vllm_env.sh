#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
LLM_SETUP_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd -P)"
cd "${LLM_SETUP_ROOT}"

RESULT_DIR="${LLM_SETUP_ROOT}/test_results/environment"
RESULT_FILE="${RESULT_DIR}/preflight.txt"
mkdir -p "${RESULT_DIR}"

{
  echo "===== vLLM environment preflight ====="
  date --iso-8601=seconds || date
  echo
  echo "===== repository and working directory ====="
  pwd
  git rev-parse --show-toplevel
  echo
  echo "===== uv and executable resolution ====="
  command -v uv
  uv --version
  uv run which python
  uv run python --version
  uv run which vllm
  echo
  echo "===== Python, vLLM, Transformers, PyTorch, and CUDA import probe ====="
  uv run python -c '
import sys
import torch
import transformers
import vllm

print("python:", sys.version)
print("vllm:", vllm.__version__)
print("transformers:", transformers.__version__)
print("torch:", torch.__version__)
print("torch CUDA:", torch.version.cuda)
print("cuda available:", torch.cuda.is_available())

if torch.cuda.is_available():
    print("device count:", torch.cuda.device_count())
    print("device:", torch.cuda.get_device_name(0))
    print("capability:", torch.cuda.get_device_capability(0))
    print("allocated:", torch.cuda.memory_allocated(0))
    print("reserved:", torch.cuda.memory_reserved(0))
'
  echo
  echo "===== NVIDIA driver and CUDA toolkit ====="
  nvidia-smi
  echo "CUDA_HOME=${CUDA_HOME:-UNSET}"
  command -v nvcc || true
  nvcc --version || true
  echo
  echo "===== relevant environment variables ====="
  env | sort | grep -E '^(CUDA|NVIDIA|VLLM|HF_|TRANSFORMERS|TORCH)' || true
  echo
  echo "===== vLLM environment collector ====="
  if uv run vllm collect-env; then
    echo "vllm collect-env: supported and completed"
  else
    echo "vllm collect-env: unsupported or failed; continuing preflight"
  fi
} >"${RESULT_FILE}" 2>&1

echo "Preflight recorded at ${RESULT_FILE}"
