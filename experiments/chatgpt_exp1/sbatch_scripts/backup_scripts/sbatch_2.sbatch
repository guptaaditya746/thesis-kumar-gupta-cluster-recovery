#!/bin/bash
#SBATCH --job-name=jupyter_neo4j_vllm
#SBATCH --output=%x_%j/stack_%j.log
#SBATCH --error=%x_%j/stack_%j.log
#SBATCH --time=08:00:00
#SBATCH --mem=32G
#SBATCH --cpus-per-task=8
#SBATCH --gres=gpu:1

set -euo pipefail

# ── Paths / Ports ─────────────────────────────────────────────────────────
LOG_DIR="$HOME/logs"
VENV="$HOME/thesis/git/kg_from_scratch/venv"

NEO4J_VERSION="5.26.0"
NEO4J_BASE="$HOME/neo4j"
NEO4J_TGZ="$NEO4J_BASE/neo4j-community-${NEO4J_VERSION}-unix.tar.gz"
NEO4J_HOME="$NEO4J_BASE/neo4j-community-${NEO4J_VERSION}"
NEO4J_URL="https://dist.neo4j.org/neo4j-community-${NEO4J_VERSION}-unix.tar.gz"

PORT_JUPYTER=8888
PORT_NEO4J_HTTP=55678
PORT_NEO4J_BOLT=55677
PORT_VLLM=8000

mkdir -p "$LOG_DIR"

# ── Unified logging: ALL script output → one timestamped master log ────────
MASTER_LOG="$LOG_DIR/stack_${SLURM_JOB_ID}.log"
exec > >(tee -a "$MASTER_LOG") 2>&1   # ← every echo/stderr goes here too

log() { echo "[$(date '+%Y-%m-%d %T')] $*"; }

export HF_HOME="${HF_HOME:-$HOME/.cache/huggingface}"
export TRANSFORMERS_CACHE="${TRANSFORMERS_CACHE:-$HF_HOME/hub}"
export HF_HUB_ENABLE_HF_TRANSFER=1

log "============================================"
log "Job ID     : ${SLURM_JOB_ID:-N/A}"
log "Node       : $(hostname)"
log "Log dir    : $LOG_DIR"
log "Master log : $MASTER_LOG"
log "GPU        : $(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null || echo 'No GPU')"
log "Java       : $(java -version 2>&1 | head -1 || echo 'No Java')"
log "Python     : $(python --version 2>&1 || true)"
log "============================================"

# ── 0) uv + venv ──────────────────────────────────────────────────────────
log "Setting up uv + venv..."
if ! command -v uv >/dev/null 2>&1; then
  python -m pip install --user -U uv
  export PATH="$HOME/.local/bin:$PATH"
fi
[ ! -d "$VENV" ] && uv venv "$VENV"
# shellcheck disable=SC1090
source "$VENV/bin/activate"
uv pip install -U jupyterlab notebook vllm neo4j pandas numpy

# ── 1) Neo4j install ───────────────────────────────────────────────────────
log "Ensuring Neo4j is present..."
if [ ! -d "$NEO4J_HOME" ]; then
  [ ! -f "$NEO4J_TGZ" ] && { log "Downloading Neo4j ${NEO4J_VERSION}..."; curl -L "$NEO4J_URL" -o "$NEO4J_TGZ"; }
  tar -xzf "$NEO4J_TGZ" -C "$NEO4J_BASE"
fi

# ── 2) Configure Neo4j ────────────────────────────────────────────────────
log "Configuring Neo4j..."
NEO4J_CONF="$NEO4J_HOME/conf/neo4j.conf"
NODE="$(hostname)"

# Point Neo4j logs to our unified log dir
declare -A NEO4J_SETTINGS=(
  ["server.default_listen_address"]="0.0.0.0"
  ["server.http.listen_address"]="0.0.0.0:${PORT_NEO4J_HTTP}"
  ["server.bolt.listen_address"]="0.0.0.0:${PORT_NEO4J_BOLT}"
  ["server.http.advertised_address"]="${NODE}:${PORT_NEO4J_HTTP}"
  ["server.bolt.advertised_address"]="${NODE}:${PORT_NEO4J_BOLT}"
  ["dbms.security.auth_enabled"]="false"
  ["server.directories.logs"]="${LOG_DIR}"   # ← Neo4j logs → same dir
)

for KEY in "${!NEO4J_SETTINGS[@]}"; do
  VAL="${NEO4J_SETTINGS[$KEY]}"
  if grep -q "^${KEY}=" "$NEO4J_CONF" 2>/dev/null; then
    sed -i "s|^${KEY}=.*|${KEY}=${VAL}|g" "$NEO4J_CONF"
  else
    echo "${KEY}=${VAL}" >> "$NEO4J_CONF"
  fi
done

# ── 3) Start Neo4j ────────────────────────────────────────────────────────
log "Starting Neo4j..."
export JAVA_HOME
JAVA_HOME="$(dirname "$(dirname "$(readlink -f "$(command -v java)")")")"
"$NEO4J_HOME/bin/neo4j" start

for i in $(seq 1 40); do
  nc -z localhost "$PORT_NEO4J_BOLT" >/dev/null 2>&1 && log "Neo4j ready!" && break
  log "  ... Neo4j waiting ($i/40)"; sleep 3
done

# ── 4) Start vLLM ─────────────────────────────────────────────────────────
log "Starting vLLM..."
vllm serve Qwen/Qwen2.5-3B-Instruct \
  --host 0.0.0.0 \
  --port "$PORT_VLLM" \
  --max-model-len 4096 \
  --gpu-memory-utilization 0.50 \
  >> "$LOG_DIR/vllm_${SLURM_JOB_ID}.log" 2>&1 &
VLLM_PID=$!
log "vLLM PID=$VLLM_PID → log: $LOG_DIR/vllm_${SLURM_JOB_ID}.log"

for i in $(seq 1 80); do
  curl -fsS "http://localhost:${PORT_VLLM}/health" >/dev/null 2>&1 && log "vLLM ready!" && break
  log "  ... vLLM waiting ($i/80)"; sleep 5
done

# ── 5) Start Jupyter ──────────────────────────────────────────────────────
log "Starting Jupyter..."
jupyter lab \
  --no-browser \
  --port="$PORT_JUPYTER" \
  --ip=0.0.0.0 \
  --ServerApp.token='mysecrettoken' \
  --ServerApp.allow_origin='*' \
  >> "$LOG_DIR/jupyter_${SLURM_JOB_ID}.log" 2>&1 &
JUPYTER_PID=$!
log "Jupyter PID=$JUPYTER_PID → log: $LOG_DIR/jupyter_${SLURM_JOB_ID}.log"

# ── 6) SSH tunnel instructions ────────────────────────────────────────────
log "============================================"
log "  ALL SERVICES RUNNING — SSH TUNNELS BELOW"
log "============================================"
log "Run on your LOCAL machine:"
log ""
log "  ssh -N \\"
log "    -L ${PORT_JUPYTER}:${NODE}:${PORT_JUPYTER} \\"
log "    -L ${PORT_NEO4J_HTTP}:${NODE}:${PORT_NEO4J_HTTP} \\"
log "    -L ${PORT_NEO4J_BOLT}:${NODE}:${PORT_NEO4J_BOLT} \\"
log "    -L ${PORT_VLLM}:${NODE}:${PORT_VLLM} \\"
log "    YOUR_USER@YOUR_CLUSTER_LOGIN_NODE"
log ""
log "Jupyter  → http://localhost:${PORT_JUPYTER}  (token: mysecrettoken)"
log "Neo4j    → http://localhost:${PORT_NEO4J_HTTP}"
log "Bolt     → bolt://localhost:${PORT_NEO4J_BOLT}"
log "vLLM API → http://localhost:${PORT_VLLM}/v1"
log "ALL LOGS → $LOG_DIR/"
log "============================================"

# ── 7) Cleanup ────────────────────────────────────────────────────────────
cleanup() {
  log "Shutting down services..."
  kill "$VLLM_PID" "$JUPYTER_PID" 2>/dev/null || true
  "$NEO4J_HOME/bin/neo4j" stop || true
  log "Done."
}
trap cleanup EXIT SIGTERM
wait "$VLLM_PID" "$JUPYTER_PID"

