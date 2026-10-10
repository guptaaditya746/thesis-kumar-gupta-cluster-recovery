#!/usr/bin/env bash
# vLLM launcher for Qwen3.5 chat + Qwen3-VL embeddings, with LiteLLM-friendly aliases.
# Keep runtime logic here. Keep tunable values in serve_qwen35_litellm.conf.

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${CONFIG_FILE:-${SCRIPT_DIR}/serve_qwen35_litellm.conf}"
RUN_ID="$(date '+%Y%m%d_%H%M%S')"

# -----------------------------
# Logging helpers
# -----------------------------
log() { printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"; }
warn() { log "WARNING: $*"; }
die() { log "ERROR: $*"; exit 1; }

mask_secret() {
  local value="${1:-}"
  if [[ -z "$value" ]]; then
    printf '<empty>'
  elif ((${#value} <= 8)); then
    printf '***'
  else
    printf '%s…%s' "${value:0:4}" "${value: -4}"
  fi
}

quote_cmd() {
  printf '%q ' "$@"
  printf '\n'
}

is_true() {
  case "${1:-0}" in
    1|true|TRUE|yes|YES|on|ON) return 0 ;;
    *) return 1 ;;
  esac
}

set_default() {
  local name="$1"
  local value="$2"
  if [[ -z "${!name:-}" ]]; then
    printf -v "$name" '%s' "$value"
  fi
}

# -----------------------------
# Load config first, then defaults.
# IMPORTANT: avoid ${VAR:-'{"json":true}'} patterns.
# A literal } inside Bash parameter expansion can become an extra brace.
# -----------------------------
if [[ -f "$CONFIG_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$CONFIG_FILE"
else
  warn "No config file found at $CONFIG_FILE; using environment variables and built-in defaults."
fi

# -----------------------------
# Defaults. Tunables belong in the .conf file.
# -----------------------------
set_default MODEL_CHAT 'Qwen/Qwen3.5-4B'
set_default MODEL_EMBED 'Qwen/Qwen3-VL-Embedding-2B'

set_default CHAT_ALIAS 'qwen-chat'
set_default EMBED_ALIAS 'qwen-embed'
set_default VLLM_API_KEY 'sk-local-vllm'

set_default PORT_CHAT '8000'
set_default PORT_EMBED '8001'

set_default MAX_MODEL_LEN_CHAT '8192'
set_default MAX_MODEL_LEN_EMBED '8192'
set_default CHAT_GPU_MEMORY_UTILIZATION '0.70'
set_default EMBED_GPU_MEMORY_UTILIZATION '0.20'

set_default START_EMBED '1'
set_default ENABLE_MTP '0'
set_default ENFORCE_EAGER '1'
set_default LOG_LEVEL 'debug'
set_default WAIT_MAX '240'         # 240 * 5 sec = 20 min
set_default HEALTH_INTERVAL '5'
set_default PREFETCH_MODELS '1'

set_default REASONING_PARSER 'qwen3'
set_default CHAT_TEMPLATE_KWARGS '{"enable_thinking":false}'
set_default SPECULATIVE_CONFIG '{"method":"mtp","num_speculative_tokens":1}'

# Add these lines for Tool Calling defaults:
set_default ENABLE_AUTO_TOOL_CHOICE '0'
set_default TOOL_CALL_PARSER ''

set_default HF_HOME "$HOME/.cache/huggingface"
set_default TRANSFORMERS_CACHE "$HF_HOME/hub"
set_default VLLM_CACHE_ROOT "$HOME/.cache/vllm"
set_default TRITON_CACHE_DIR "$HOME/.cache/triton"
set_default TORCHINDUCTOR_CACHE_DIR "$HOME/.cache/torch_inductor"
set_default HF_HUB_OFFLINE '0'
set_default HF_XET_HIGH_PERFORMANCE '1'
set_default OMP_NUM_THREADS '8'

set_default VLLM_USE_V1 '0'
set_default VLLM_ATTENTION_BACKEND 'FLASH_ATTN'
set_default VLLM_USE_FLASHINFER_SAMPLER '0'

set_default GPU_CHAT '0'
set_default GPU_EMBED '0'
set_default LOG_DIR "$SCRIPT_DIR"

mkdir -p "$LOG_DIR"
LAUNCHER_LOG="${LOG_DIR}/launcher_${RUN_ID}.log"
exec > >(tee -a "$LAUNCHER_LOG") 2>&1

log "Loaded config: $CONFIG_FILE"
log "Launcher log: $LAUNCHER_LOG"

# -----------------------------
# Export runtime environment
# -----------------------------
export MODEL_CHAT MODEL_EMBED
export HF_HOME TRANSFORMERS_CACHE VLLM_CACHE_ROOT TRITON_CACHE_DIR TORCHINDUCTOR_CACHE_DIR
export HF_HUB_OFFLINE HF_XET_HIGH_PERFORMANCE OMP_NUM_THREADS
export VLLM_USE_V1 VLLM_ATTENTION_BACKEND VLLM_USE_FLASHINFER_SAMPLER

mkdir -p \
  "$HF_HOME" \
  "$TRANSFORMERS_CACHE" \
  "$VLLM_CACHE_ROOT" \
  "$TRITON_CACHE_DIR" \
  "$TORCHINDUCTOR_CACHE_DIR"

# Avoid the deprecated Hugging Face variable if it leaked from the outer environment.
unset HF_HUB_ENABLE_HF_TRANSFER || true

# -----------------------------
# Validation / diagnostics
# -----------------------------
require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "Required command not found: $1"
}

validate_json_var() {
  local name="$1"
  local value="${!name:-}"
  [[ -z "$value" ]] && return 0
  VALUE="$value" python - <<'PY' || exit 1
import json, os, sys
try:
    json.loads(os.environ["VALUE"])
except Exception as e:
    print(f"invalid JSON: {e}", file=sys.stderr)
    sys.exit(1)
PY
}

check_port_free() {
  local port="$1"
  if command -v ss >/dev/null 2>&1; then
    if ss -ltn | awk '{print $4}' | grep -qE "[:.]${port}$"; then
      die "port ${port} is already in use"
    fi
  elif command -v lsof >/dev/null 2>&1; then
    if lsof -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
      die "port ${port} is already in use"
    fi
  else
    warn "Neither ss nor lsof is available; skipping port check for ${port}."
  fi
}

check_memory_budget() {
  if is_true "$START_EMBED" && [[ "$GPU_CHAT" == "$GPU_EMBED" ]]; then
    CHAT_GPU_MEMORY_UTILIZATION="$CHAT_GPU_MEMORY_UTILIZATION" \
    EMBED_GPU_MEMORY_UTILIZATION="$EMBED_GPU_MEMORY_UTILIZATION" python - <<'PY' || exit 1
import os, sys
chat = float(os.environ["CHAT_GPU_MEMORY_UTILIZATION"])
embed = float(os.environ["EMBED_GPU_MEMORY_UTILIZATION"])
total = chat + embed
if total > 0.95:
    print(f"ERROR: chat+embed gpu-memory-utilization={total:.2f} on one GPU. Keep <= 0.95 or use separate GPUs.", file=sys.stderr)
    sys.exit(1)
print(f"GPU memory budget on shared GPU: chat={chat:.2f}, embed={embed:.2f}, total={total:.2f}")
PY
  fi
}

print_config_summary() {
  log "============================================"
  log "Run ID: $RUN_ID"
  log "Node: $(hostname -f 2>/dev/null || hostname)"
  log "PWD: $(pwd)"
  log "Script dir: $SCRIPT_DIR"
  log "Python: $(command -v python || true)"
  log "vLLM: $(command -v vllm || true)"
  log "API key: $(mask_secret "$VLLM_API_KEY")"
  log ""
  log "Chat model: $MODEL_CHAT"
  log "Chat alias: $CHAT_ALIAS"
  log "Chat port: $PORT_CHAT"
  log "Chat GPU: $GPU_CHAT"
  log "Chat max length: $MAX_MODEL_LEN_CHAT"
  log "Chat GPU memory util: $CHAT_GPU_MEMORY_UTILIZATION"
  log "Reasoning parser: ${REASONING_PARSER:-<disabled>}"
  log "Chat template kwargs: ${CHAT_TEMPLATE_KWARGS:-<none>}"
  log ""
  log "Embedding enabled: $START_EMBED"
  log "Embedding model: $MODEL_EMBED"
  log "Embedding alias: $EMBED_ALIAS"
  log "Embedding port: $PORT_EMBED"
  log "Embedding GPU: $GPU_EMBED"
  log "Embedding max length: $MAX_MODEL_LEN_EMBED"
  log "Embedding GPU memory util: $EMBED_GPU_MEMORY_UTILIZATION"
  log ""
  log "LOG_LEVEL: $LOG_LEVEL"
  log "ENFORCE_EAGER: $ENFORCE_EAGER"
  log "ENABLE_MTP: $ENABLE_MTP"
  log "PREFETCH_MODELS: $PREFETCH_MODELS"
  log "WAIT_MAX: $WAIT_MAX"
  log "HEALTH_INTERVAL: $HEALTH_INTERVAL"
  log "HF_XET_HIGH_PERFORMANCE: $HF_XET_HIGH_PERFORMANCE"
  log "VLLM_ATTENTION_BACKEND: $VLLM_ATTENTION_BACKEND"
  log "VLLM_USE_V1: $VLLM_USE_V1"
  log "============================================"
}

print_python_diagnostics() {
  python - <<'PY'
import os, sys
print("python:", sys.executable)
try:
    import torch
    print("torch:", torch.__version__)
    print("cuda available:", torch.cuda.is_available())
    print("torch cuda:", torch.version.cuda)
    if torch.cuda.is_available():
        print("gpu count:", torch.cuda.device_count())
        for idx in range(torch.cuda.device_count()):
            print(f"gpu[{idx}]:", torch.cuda.get_device_name(idx), "capability", torch.cuda.get_device_capability(idx))
except Exception as e:
    print("torch check failed:", repr(e))

try:
    import vllm
    print("vllm:", vllm.__version__)
except Exception as e:
    print("vllm import failed:", repr(e))

try:
    import huggingface_hub
    print("huggingface_hub:", huggingface_hub.__version__)
except Exception as e:
    print("huggingface_hub import failed:", repr(e))

for name in [
    "HF_HOME", "TRANSFORMERS_CACHE", "VLLM_CACHE_ROOT", "TRITON_CACHE_DIR",
    "TORCHINDUCTOR_CACHE_DIR", "HF_HUB_OFFLINE", "HF_XET_HIGH_PERFORMANCE",
    "VLLM_USE_V1", "VLLM_ATTENTION_BACKEND", "VLLM_USE_FLASHINFER_SAMPLER",
]:
    print(f"{name}={os.environ.get(name, '')}")
PY
}

# -----------------------------
# CUDA linker workaround for FlashInfer / Ninja JIT
# -----------------------------
setup_cuda_link() {
  local workdir cuda_lib cuda_lib_dir cuda_link_dir
  workdir="$(pwd)"
  cuda_lib="$(ldconfig -p 2>/dev/null | awk '/libcuda\.so\.1/{print $NF; exit}' || true)"

  if [[ -z "$cuda_lib" ]]; then
    cuda_lib="$(find /usr /lib /lib64 -name 'libcuda.so.1' 2>/dev/null | head -n 1 || true)"
  fi

  if [[ -n "$cuda_lib" ]]; then
    cuda_lib_dir="$(dirname "$cuda_lib")"
    cuda_link_dir="${workdir}/.cuda-link"
    mkdir -p "$cuda_link_dir"
    ln -sf "$cuda_lib" "${cuda_link_dir}/libcuda.so"

    export LIBRARY_PATH="${cuda_link_dir}:${cuda_lib_dir}:${LIBRARY_PATH:-}"
    export LD_LIBRARY_PATH="${cuda_link_dir}:${cuda_lib_dir}:${LD_LIBRARY_PATH:-}"

    log "CUDA_LIB=$cuda_lib"
    log "CUDA_LINK_DIR=$cuda_link_dir"
  else
    warn "libcuda.so.1 not found. vLLM may fail if FlashInfer tries to compile."
  fi
}

# -----------------------------
# Server lifecycle
# -----------------------------
PIDS=()
NAMES=()
LOGFILES=()
LAST_PID=""

cleanup() {
  local code=$?
  if ((${#PIDS[@]} > 0)); then
    log "Stopping vLLM servers..."
    for pid in "${PIDS[@]}"; do
      kill "$pid" 2>/dev/null || true
    done
    for pid in "${PIDS[@]}"; do
      wait "$pid" 2>/dev/null || true
    done
    log "Stopped."
  fi
  exit "$code"
}
trap cleanup EXIT SIGINT SIGTERM

wait_health() {
  local name="$1"
  local port="$2"
  local logfile="$3"
  local pid="$4"

  log "Waiting for ${name} /health on port ${port}; pid=${pid}; log=${logfile}"

  for i in $(seq 1 "$WAIT_MAX"); do
    if curl -fsS "http://127.0.0.1:${port}/health" >/dev/null 2>&1; then
      log "${name} ready after $((i * HEALTH_INTERVAL)) seconds."
      curl -fsS "http://127.0.0.1:${port}/v1/models" \
        -H "Authorization: Bearer ${VLLM_API_KEY}" >/dev/null 2>&1 \
        && log "${name} /v1/models reachable." \
        || warn "${name} /v1/models check failed, but /health is OK."
      return 0
    fi

    if ! kill -0 "$pid" 2>/dev/null; then
      log "${name} exited early. Last 200 log lines from ${logfile}:"
      tail -n 200 "$logfile" || true
      return 1
    fi

    sleep "$HEALTH_INTERVAL"
  done

  log "${name} did not become healthy. Last 200 log lines from ${logfile}:"
  tail -n 200 "$logfile" || true
  return 1
}

start_server() {
  local name="$1"
  local gpu="$2"
  local logfile="$3"
  shift 3

  rm -f "$logfile"
  log "Starting ${name}. Log: ${logfile}"
  log "Command: $(quote_cmd env CUDA_VISIBLE_DEVICES="$gpu" vllm serve "$@")"

  CUDA_VISIBLE_DEVICES="$gpu" vllm serve "$@" >"$logfile" 2>&1 &
  LAST_PID="$!"
  PIDS+=("$LAST_PID")
  NAMES+=("$name")
  LOGFILES+=("$logfile")
  log "${name} PID=${LAST_PID}"
}

prefetch_model() {
  local label="$1"
  local repo_id="$2"

  if ! is_true "$PREFETCH_MODELS"; then
    log "PREFETCH_MODELS=0, skipping ${label} prefetch."
    return 0
  fi

  log "Prefetching ${label} model: ${repo_id}"
  REPO_ID="$repo_id" python - <<'PY'
import os
from huggingface_hub import snapshot_download
repo_id = os.environ["REPO_ID"]
snapshot_download(repo_id=repo_id)
print(f"prefetch done: {repo_id}")
PY
}

# -----------------------------
# Preflight
# -----------------------------
require_cmd python
require_cmd curl
require_cmd vllm

validate_json_var CHAT_TEMPLATE_KWARGS || die "CHAT_TEMPLATE_KWARGS must be valid JSON: ${CHAT_TEMPLATE_KWARGS}"
if is_true "$ENABLE_MTP"; then
  validate_json_var SPECULATIVE_CONFIG || die "SPECULATIVE_CONFIG must be valid JSON: ${SPECULATIVE_CONFIG}"
fi

check_port_free "$PORT_CHAT"
if is_true "$START_EMBED"; then
  check_port_free "$PORT_EMBED"
fi
check_memory_budget
setup_cuda_link
print_config_summary
print_python_diagnostics
nvidia-smi || warn "nvidia-smi failed or is unavailable."

prefetch_model "chat" "$MODEL_CHAT"
if is_true "$START_EMBED"; then
  prefetch_model "embedding" "$MODEL_EMBED"
fi

# -----------------------------
# Chat server
# -----------------------------
CHAT_LOG="${LOG_DIR}/vllm_chat_${CHAT_ALIAS}_${PORT_CHAT}.log"
CHAT_ARGS=(
  "$MODEL_CHAT"
  --host 0.0.0.0
  --port "$PORT_CHAT"
  --dtype auto
  --max-model-len "$MAX_MODEL_LEN_CHAT"
  --gpu-memory-utilization "$CHAT_GPU_MEMORY_UTILIZATION"
  --served-model-name "$CHAT_ALIAS"
  --api-key "$VLLM_API_KEY"
  --safetensors-load-strategy prefetch
)

if is_true "$ENFORCE_EAGER"; then
  CHAT_ARGS+=(--enforce-eager)
fi

if [[ -n "${REASONING_PARSER:-}" ]]; then
  CHAT_ARGS+=(--reasoning-parser "$REASONING_PARSER")
fi

if [[ -n "${CHAT_TEMPLATE_KWARGS:-}" ]]; then
  CHAT_ARGS+=(--default-chat-template-kwargs "$CHAT_TEMPLATE_KWARGS")
fi

if is_true "$ENABLE_MTP"; then
  CHAT_ARGS+=(--speculative-config "$SPECULATIVE_CONFIG")
fi

if is_true "$ENABLE_AUTO_TOOL_CHOICE"; then
  CHAT_ARGS+=(--enable-auto-tool-choice)
fi

if [[ -n "${TOOL_CALL_PARSER:-}" ]]; then
  CHAT_ARGS+=(--tool-call-parser "$TOOL_CALL_PARSER")
fi

start_server "Chat" "$GPU_CHAT" "$CHAT_LOG" "${CHAT_ARGS[@]}"
CHAT_PID="$LAST_PID"
wait_health "Chat" "$PORT_CHAT" "$CHAT_LOG" "$CHAT_PID" || die "Chat server failed health check."

# -----------------------------
# Embedding server
# -----------------------------
if is_true "$START_EMBED"; then
  EMBED_LOG="${LOG_DIR}/vllm_embed_${EMBED_ALIAS}_${PORT_EMBED}.log"
  EMBED_ARGS=(
    "$MODEL_EMBED"
    --host 0.0.0.0
    --port "$PORT_EMBED"
    --runner pooling
    --dtype auto
    --max-model-len "$MAX_MODEL_LEN_EMBED"
    --gpu-memory-utilization "$EMBED_GPU_MEMORY_UTILIZATION"
    --served-model-name "$EMBED_ALIAS"
    --api-key "$VLLM_API_KEY"
    --trust-remote-code
    --safetensors-load-strategy prefetch
  )

  if is_true "$ENFORCE_EAGER"; then
    EMBED_ARGS+=(--enforce-eager)
  fi

  start_server "Embeddings" "$GPU_EMBED" "$EMBED_LOG" "${EMBED_ARGS[@]}"
  EMBED_PID="$LAST_PID"
  wait_health "Embeddings" "$PORT_EMBED" "$EMBED_LOG" "$EMBED_PID" || die "Embedding server failed health check."
else
  log "START_EMBED=0, embedding server skipped."
fi

NODE="$(hostname -f 2>/dev/null || hostname)"

log "============================================"
log "vLLM servers are running."
log ""
log "Chat:"
log "  LiteLLM model : openai/${CHAT_ALIAS}"
log "  vLLM name     : ${CHAT_ALIAS}"
log "  local base    : http://127.0.0.1:${PORT_CHAT}/v1"
log "  remote base   : http://${NODE}:${PORT_CHAT}/v1"
log "  log file      : ${CHAT_LOG}"
log ""

if is_true "$START_EMBED"; then
  log "Embeddings:"
  log "  LiteLLM model : openai/${EMBED_ALIAS}"
  log "  vLLM name     : ${EMBED_ALIAS}"
  log "  local base    : http://127.0.0.1:${PORT_EMBED}/v1"
  log "  remote base   : http://${NODE}:${PORT_EMBED}/v1"
  log "  log file      : ${EMBED_LOG}"
  log ""
fi

log "Test chat:"
log "curl http://127.0.0.1:${PORT_CHAT}/v1/chat/completions \\"
log "  -H 'Authorization: Bearer ${VLLM_API_KEY}' \\"
log "  -H 'Content-Type: application/json' \\"
log "  -d '{\"model\":\"${CHAT_ALIAS}\",\"messages\":[{\"role\":\"user\",\"content\":\"Say hello in one sentence.\"}],\"max_tokens\":64}'"
log ""

if is_true "$START_EMBED"; then
  log "Test embeddings:"
  log "curl http://127.0.0.1:${PORT_EMBED}/v1/embeddings \\"
  log "  -H 'Authorization: Bearer ${VLLM_API_KEY}' \\"
  log "  -H 'Content-Type: application/json' \\"
  log "  -d '{\"model\":\"${EMBED_ALIAS}\",\"input\":\"GraphRAG query to knowledge graph retrieval\"}'"
  log ""
fi

log "LiteLLM config file stays separate: ${SCRIPT_DIR}/litellm_config.yaml"
log "============================================"

wait "${PIDS[@]}"
