#!/bin/bash
#SBATCH --job-name=jupyter_neo4j_vllm
#SBATCH --output=/home/%u/logs/stack_%j.log
#SBATCH --error=/home/%u/logs/stack_%j.err
#SBATCH --time=08:00:00
#SBATCH --mem=32G
#SBATCH --cpus-per-task=8
#SBATCH --gres=gpu:1

set -euo pipefail

# ── Paths / Ports ────────────────────────────────────────────────────────────
LOG_DIR="$HOME/logs"
VENV="$HOME/vllm-env"

NEO4J_VERSION="5.26.0"
NEO4J_BASE="$HOME/neo4j"
NEO4J_TGZ="$NEO4J_BASE/neo4j-community-${NEO4J_VERSION}-unix.tar.gz"
NEO4J_HOME="$NEO4J_BASE/neo4j-community-${NEO4J_VERSION}"
NEO4J_URL="https://dist.neo4j.org/neo4j-community-${NEO4J_VERSION}-unix.tar.gz"

PORT_JUPYTER=8888
PORT_NEO4J_HTTP=55678
PORT_NEO4J_BOLT=55677
PORT_VLLM=8000

mkdir -p "$LOG_DIR" "$NEO4J_BASE"

# Optional: cache HF models on shared storage if you have it
export HF_HOME="${HF_HOME:-$HOME/.cache/huggingface}"
export TRANSFORMERS_CACHE="${TRANSFORMERS_CACHE:-$HF_HOME/hub}"
export HF_HUB_ENABLE_HF_TRANSFER=1

echo "============================================"
echo "Job ID     : ${SLURM_JOB_ID:-N/A}"
echo "Node       : $(hostname)"
echo "Start time : $(date)"
echo "GPU        : $(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null || echo 'No GPU')"
echo "Java       : $(java -version 2>&1 | head -1 || echo 'No Java in PATH')"
echo "Python     : $(python --version 2>&1 || true)"
echo "============================================"

# ── 0) Setup uv venv + install Python deps ───────────────────────────────────
echo "[$(date +%T)] Setting up uv + venv..."

# If uv isn’t available, install it to user site (common on clusters)
if ! command -v uv >/dev/null 2>&1; then
  python -m pip install --user -U uv
  export PATH="$HOME/.local/bin:$PATH"
fi

# Create venv if missing
if [ ! -d "$VENV" ]; then
  uv venv "$VENV"
fi
# shellcheck disable=SC1090
source "$VENV/bin/activate"

# Install packages (idempotent)
uv pip install -U \
  jupyterlab notebook \
  vllm \
  neo4j \
  pandas numpy

# ── 1) Ensure Neo4j server exists (tarball install) ─────────────────────────
echo "[$(date +%T)] Ensuring Neo4j server is present..."
if [ ! -d "$NEO4J_HOME" ]; then
  if [ ! -f "$NEO4J_TGZ" ]; then
    echo "[$(date +%T)] Downloading Neo4j ${NEO4J_VERSION}..."
    curl -L "$NEO4J_URL" -o "$NEO4J_TGZ"
  fi
  tar -xzf "$NEO4J_TGZ" -C "$NEO4J_BASE"
fi

# ── 2) Configure Neo4j ports/bindings for THIS job ───────────────────────────
echo "[$(date +%T)] Configuring Neo4j..."
NEO4J_CONF="$NEO4J_HOME/conf/neo4j.conf"
NODE="$(hostname)"

# Make neo4j.conf edits safely:
# - Listen on all interfaces (required for SSH tunnel to work cleanly)
# - Set your custom HTTP/BOLT ports
# - Set advertised addresses to node hostname (helps drivers, even though tunneling is used)
# - Disable auth (optional). If you need auth, remove dbms.security.auth_enabled=false.
grep -q '^server.default_listen_address=' "$NEO4J_CONF" 2>/dev/null || echo "" >> "$NEO4J_CONF"
grep -q '^server.http.listen_address=' "$NEO4J_CONF" 2>/dev/null || echo "" >> "$NEO4J_CONF"
grep -q '^server.bolt.listen_address=' "$NEO4J_CONF" 2>/dev/null || echo "" >> "$NEO4J_CONF"
grep -q '^server.http.advertised_address=' "$NEO4J_CONF" 2>/dev/null || echo "" >> "$NEO4J_CONF"
grep -q '^server.bolt.advertised_address=' "$NEO4J_CONF" 2>/dev/null || echo "" >> "$NEO4J_CONF"
grep -q '^dbms.security.auth_enabled=' "$NEO4J_CONF" 2>/dev/null || echo "" >> "$NEO4J_CONF"

# Replace-or-add settings (simple sed approach)
sed -i \
  -e "s|^server.default_listen_address=.*|server.default_listen_address=0.0.0.0|g" \
  -e "s|^server.http.listen_address=.*|server.http.listen_address=0.0.0.0:${PORT_NEO4J_HTTP}|g" \
  -e "s|^server.bolt.listen_address=.*|server.bolt.listen_address=0.0.0.0:${PORT_NEO4J_BOLT}|g" \
  -e "s|^server.http.advertised_address=.*|server.http.advertised_address=${NODE}:${PORT_NEO4J_HTTP}|g" \
  -e "s|^server.bolt.advertised_address=.*|server.bolt.advertised_address=${NODE}:${PORT_NEO4J_BOLT}|g" \
  -e "s|^dbms.security.auth_enabled=.*|dbms.security.auth_enabled=false|g" \
  "$NEO4J_CONF"

# If those keys weren't present before, sed won't add them, so append if missing:
grep -q '^server.default_listen_address=' "$NEO4J_CONF" || echo "server.default_listen_address=0.0.0.0" >> "$NEO4J_CONF"
grep -q '^server.http.listen_address=' "$NEO4J_CONF" || echo "server.http.listen_address=0.0.0.0:${PORT_NEO4J_HTTP}" >> "$NEO4J_CONF"
grep -q '^server.bolt.listen_address=' "$NEO4J_CONF" || echo "server.bolt.listen_address=0.0.0.0:${PORT_NEO4J_BOLT}" >> "$NEO4J_CONF"
grep -q '^server.http.advertised_address=' "$NEO4J_CONF" || echo "server.http.advertised_address=${NODE}:${PORT_NEO4J_HTTP}" >> "$NEO4J_CONF"
grep -q '^server.bolt.advertised_address=' "$NEO4J_CONF" || echo "server.bolt.advertised_address=${NODE}:${PORT_NEO4J_BOLT}" >> "$NEO4J_CONF"
grep -q '^dbms.security.auth_enabled=' "$NEO4J_CONF" || echo "dbms.security.auth_enabled=false" >> "$NEO4J_CONF"

# ── 3) Start Neo4j ───────────────────────────────────────────────────────────
echo "[$(date +%T)] Starting Neo4j..."
export JAVA_HOME
JAVA_HOME="$(dirname "$(dirname "$(readlink -f "$(command -v java)")")")"
"$NEO4J_HOME/bin/neo4j" start

echo "[$(date +%T)] Neo4j starting → http://${NODE}:${PORT_NEO4J_HTTP}"

echo "[$(date +%T)] Waiting for Neo4j bolt port..."
for i in $(seq 1 40); do
  (nc -z localhost "$PORT_NEO4J_BOLT" >/dev/null 2>&1) && echo "[$(date +%T)] Neo4j is ready!" && break
  echo "  ... waiting ($i/40)"
  sleep 3
done

# ── 4) Start vLLM (Qwen) ────────────────────────────────────────────────────
echo "[$(date +%T)] Starting vLLM..."
# IMPORTANT: no inline comments after backslashes
vllm serve Qwen/Qwen2.5-3B-Instruct \
  --host 0.0.0.0 \
  --port "$PORT_VLLM" \
  --max-model-len 4096 \
  --gpu-memory-utilization 0.50 \
  > "$LOG_DIR/vllm_${SLURM_JOB_ID}.log" 2>&1 &
VLLM_PID=$!
echo "[$(date +%T)] vLLM PID=$VLLM_PID → http://${NODE}:${PORT_VLLM}"

echo "[$(date +%T)] Waiting for vLLM /health..."
for i in $(seq 1 80); do
  if curl -fsS "http://localhost:${PORT_VLLM}/health" >/dev/null 2>&1; then
    echo "[$(date +%T)] vLLM is ready!"
    break
  fi
  echo "  ... waiting ($i/80)"
  sleep 5
done

# ── 5) Start Jupyter ─────────────────────────────────────────────────────────
echo "[$(date +%T)] Starting Jupyter..."
jupyter lab \
  --no-browser \
  --port="$PORT_JUPYTER" \
  --ip=0.0.0.0 \
  --ServerApp.token='mysecrettoken' \
  --ServerApp.allow_origin='*' \
  > "$LOG_DIR/jupyter_${SLURM_JOB_ID}.log" 2>&1 &
JUPYTER_PID=$!
echo "[$(date +%T)] Jupyter PID=$JUPYTER_PID"

# ── 6) Print SSH tunnel instructions ─────────────────────────────────────────
echo ""
echo "============================================"
echo "  ALL SERVICES RUNNING — SSH TUNNELS BELOW"
echo "============================================"
echo "Run this on your LOCAL machine:"
echo ""
echo "  ssh -N \\"
echo "    -L ${PORT_JUPYTER}:${NODE}:${PORT_JUPYTER} \\"
echo "    -L ${PORT_NEO4J_HTTP}:${NODE}:${PORT_NEO4J_HTTP} \\"
echo "    -L ${PORT_NEO4J_BOLT}:${NODE}:${PORT_NEO4J_BOLT} \\"
echo "    -L ${PORT_VLLM}:${NODE}:${PORT_VLLM} \\"
echo "    YOUR_USER@YOUR_CLUSTER_LOGIN_NODE"
echo ""
echo "Jupyter  → http://localhost:${PORT_JUPYTER}  (token: mysecrettoken)"
echo "Neo4j    → http://localhost:${PORT_NEO4J_HTTP}"
echo "Bolt     → bolt://localhost:${PORT_NEO4J_BOLT}"
echo "vLLM API → http://localhost:${PORT_VLLM}/v1"
echo "Logs     → $LOG_DIR"
echo "============================================"

# ── 7) Cleanup ───────────────────────────────────────────────────────────────
cleanup() {
  echo "[$(date +%T)] Shutting down services..."
  kill "$VLLM_PID" "$JUPYTER_PID" 2>/dev/null || true
  "$NEO4J_HOME/bin/neo4j" stop || true
  echo "[$(date +%T)] Done."
}
trap cleanup EXIT SIGTERM

wait "$VLLM_PID" "$JUPYTER_PID"

