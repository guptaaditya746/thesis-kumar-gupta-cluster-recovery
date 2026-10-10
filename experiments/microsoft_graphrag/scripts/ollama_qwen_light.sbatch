#!/usr/bin/env bash
#SBATCH --job-name=vllm-qwen-chat-embed
#SBATCH --partition=gpu
#SBATCH --nodes=1
#SBATCH --gres=gpu:2
#SBATCH --cpus-per-task=12
#SBATCH --mem=48G
#SBATCH --time=24:00:00
#SBATCH --output=%x_%j.log
#SBATCH --error=%x_%j.log

set -euo pipefail
log() { echo "[$(date '+%Y-%m-%d %T')] $*"; }

# ---- paths ----
WORKDIR="/home/gupt_ad/thesis/thesis-kumar-gupta/experiments/litellm"
VENV_DIR="${WORKDIR}/.venv"

cd "$WORKDIR"
# shellcheck disable=SC1090
source "${VENV_DIR}/bin/activate"

log "Node: $(hostname)"
log "Python: $(which python)"
python -c 'import torch; print("torch:", torch.__version__, "cuda available:", torch.cuda.is_available(), "cuda:", torch.version.cuda)'
nvidia-smi || true

# ---- ports (deterministic per job) ----
JOB_NUM="${SLURM_JOB_ID:-99999}"
BASE=$(( 40000 + (JOB_NUM % 20000) ))
PORT_CHAT="${PORT_CHAT:-$((BASE + 4))}"
PORT_EMBED="${PORT_EMBED:-$((BASE + 5))}"
log "Ports: chat=$PORT_CHAT embed=$PORT_EMBED"

# ---- HF cache (persistent recommended) ----
export HF_HOME="${HF_HOME:-$HOME/.cache/huggingface}"
export TRANSFORMERS_CACHE="${TRANSFORMERS_CACHE:-$HF_HOME/hub}"
mkdir -p "$HF_HOME" "$TRANSFORMERS_CACHE"
log "HF_HOME: $HF_HOME"

# ---- models ----
export MODEL_CHAT="${MODEL_CHAT:-Qwen/Qwen2.5-3B-Instruct}"
export MODEL_EMBED="${MODEL_EMBED:-Qwen/Qwen3-Embedding-0.6B}"

log "Chat model : $MODEL_CHAT"
log "Embed model: $MODEL_EMBED"

# ---- prefetch both models (download/extract into HF cache) ----
log "Prefetching chat model..."
python - <<'PY'
import os
from huggingface_hub import snapshot_download
snapshot_download(repo_id=os.environ["MODEL_CHAT"], resume_download=True)
print("Chat prefetch done.")
PY

log "Prefetching embedding model..."
python - <<'PY'
import os
from huggingface_hub import snapshot_download
snapshot_download(repo_id=os.environ["MODEL_EMBED"], resume_download=True)
print("Embed prefetch done.")
PY

# ---- start vLLM: chat on GPU0 ----
CHAT_LOG="vllm_chat_${SLURM_JOB_ID}.log"
log "Starting vLLM chat (GPU0) log=$CHAT_LOG ..."
CUDA_VISIBLE_DEVICES=0 vllm serve "$MODEL_CHAT" \
  --host 0.0.0.0 \
  --port "$PORT_CHAT" \
  --dtype auto \
  --max-model-len "${MAX_MODEL_LEN:-32768}" \
  --gpu-memory-utilization "${GPU_MEM_UTIL_CHAT:-0.90}" \
  >> "$CHAT_LOG" 2>&1 &
PID_CHAT=$!

# ---- start vLLM: embeddings on GPU1 ----
EMBED_LOG="vllm_embed_${SLURM_JOB_ID}.log"
log "Starting vLLM embeddings (GPU1) log=$EMBED_LOG ..."
CUDA_VISIBLE_DEVICES=1 vllm serve "$MODEL_EMBED" \
  --host 0.0.0.0 \
  --port "$PORT_EMBED" \
  --dtype auto \
  --max-model-len 8192 \
  --gpu-memory-utilization "${GPU_MEM_UTIL_EMBED:-0.80}" \
  >> "$EMBED_LOG" 2>&1 &
PID_EMBED=$!

cleanup () {
  log "Shutting down vLLM..."
  kill "$PID_CHAT" "$PID_EMBED" 2>/dev/null || true
  wait "$PID_CHAT" 2>/dev/null || true
  wait "$PID_EMBED" 2>/dev/null || true
  log "Done."
}
trap cleanup EXIT SIGTERM SIGINT

# ---- wait until healthy ----
log "Waiting for chat /health..."
for i in $(seq 1 120); do
  curl -fsS "http://localhost:${PORT_CHAT}/health" >/dev/null 2>&1 && log "Chat ready!" && break
  sleep 5
  if [[ "$i" -eq 120 ]]; then
    log "Chat failed. Last 80 lines:"
    tail -n 80 "$CHAT_LOG" || true
    exit 1
  fi
done

log "Waiting for embed /health..."
for i in $(seq 1 120); do
  curl -fsS "http://localhost:${PORT_EMBED}/health" >/dev/null 2>&1 && log "Embeddings ready!" && break
  sleep 5
  if [[ "$i" -eq 120 ]]; then
    log "Embeddings failed. Last 80 lines:"
    tail -n 80 "$EMBED_LOG" || true
    exit 1
  fi
done

NODE="$(hostname -f 2>/dev/null || hostname)"
log "============================================"
log "Chat API     : http://${NODE}:${PORT_CHAT}   (OpenAI-style at /v1)"
log "Embeddings API: http://${NODE}:${PORT_EMBED} (OpenAI-style at /v1)"
log ""
log "Tunnel from laptop (example):"
log "ssh -N \\"
log "  -L ${PORT_CHAT}:${NODE}:${PORT_CHAT} \\"
log "  -L ${PORT_EMBED}:${NODE}:${PORT_EMBED} \\"
log "  gupt_ad@LOGIN_NODE"
log "Then use:"
log "  Chat      base_url: http://localhost:${PORT_CHAT}/v1"
log "  Embedding base_url: http://localhost:${PORT_EMBED}/v1"
log "============================================"

wait "$PID_CHAT" "$PID_EMBED"
