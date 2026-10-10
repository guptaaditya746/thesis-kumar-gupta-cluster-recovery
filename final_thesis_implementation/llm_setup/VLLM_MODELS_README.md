# vLLM model manager

This is the entry point for running one or two concurrent vLLM chat backends plus an embedding backend. It does not run Pi Bench or other benchmarks.

## Environment

```text
Python: 3.13.9
vLLM: 0.21.0
PyTorch: 2.11.0+cu130
GPU: NVIDIA A100-SXM4-40GB
Environment: PASS
```

## Setup

```bash
cd ~/thesis/thesis-kumar-gupta/final_thesis_implementation/llm_setup
export VLLM_API_KEY="sk-local-vllm"
```
The user-verified `hkust-nlp/WebExplorer-8B` profile is available as `webexplorer-8b`:

```bash
./scripts/vllm-model show webexplorer-8b
./scripts/vllm-model start webexplorer-8b
```

It uses the cached local snapshot, 32,768-token context, eager execution, `TRITON_ATTN`, Qwen3 reasoning parsing, and Hermes tool parsing.


The model registry is [config/vllm_models.toml](config/vllm_models.toml). Each profile contains its complete vLLM command, so parser, reasoning, context, and quantization flags are not inherited from another model.

## Chat models

```bash
./scripts/vllm-model list
./scripts/vllm-model show qwen3-8b
./scripts/vllm-model start qwen3-8b
./scripts/vllm-model status
./scripts/vllm-model health
./scripts/vllm-model chat "Reply briefly and confirm that the model is running."
./scripts/vllm-model switch qwen25-14b
./scripts/vllm-model shutdown
```

The tested Qwen3.8 INT8 MTP profile is available as `qwen38-27b-int8-mtp`:

```bash
./scripts/vllm-model show qwen38-27b-int8-mtp
./scripts/vllm-model start qwen38-27b-int8-mtp
```

It uses an 8,192-token context, one sequence, `TRITON_ATTN`, eager execution, the Qwen3 reasoning parser, and the Qwen3-Coder tool parser. It was verified by the user with a successful chat response.

The manager supports a pair of concurrent chat models: a heavy backend on vLLM port 8002 and a lite backend on port 8003. It starts one LiteLLM gateway on port 4000:

```text
Base URL: http://127.0.0.1:4000/v1
Models: heavy-model, lite-model (qwen-chat remains a compatibility alias)
API key: sk-local-vllm
```

Direct vLLM access is `http://127.0.0.1:8002/v1`.

## Concurrent heavy/lite chat models

Start two configurable profiles behind the same LiteLLM gateway:

```bash
./scripts/vllm-model start-pair qwen3-30b-thinking-fp8 qwen3-8b
./scripts/vllm-model status
./scripts/vllm-model chat --model heavy-model "Use the heavy model."
./scripts/vllm-model chat --model lite-model "Use the lite model."
./scripts/vllm-model stop-pair
```

The heavy and lite backends use ports `8002` and `8003`, on CUDA devices `0` and `1` respectively. Both vLLM servers and LiteLLM authenticate with `VLLM_API_KEY`; set it before startup. Pair startup applies configured per-process GPU budgets and rolls back both backends if either one fails.

Clients use `http://127.0.0.1:4000/v1` with model `heavy-model` or `lite-model`.

## Embedding models

Embedding models run on port 8001 and may run alongside the heavy and lite chat backends on ports 8002 and 8003. Both services share the A100, so reduce their per-process GPU-memory settings if startup reports CUDA or KV-cache OOM.

```bash
./scripts/vllm-model embed list
./scripts/vllm-model embed show qwen3-embedding-0.6b
./scripts/vllm-model embed start qwen3-embedding-0.6b
./scripts/vllm-model embed test
./scripts/vllm-model embed stop
```

LiteLLM uses model `qwen-embed` at `http://127.0.0.1:4000/v1`. Direct vLLM embeddings use `http://127.0.0.1:8001/v1`.

The manager allows chat and embedding backends to run simultaneously. It still refuses to stop processes it did not start.

## LiteLLM

LiteLLM configuration is [config/litellm.yaml](config/litellm.yaml). It starts automatically with a backend.

```bash
./scripts/vllm-model gateway start
./scripts/vllm-model gateway stop
```

LiteLLM only provides stable routing. It does not select vLLM reasoning parsers, tool parsers, chat templates, context lengths, or quantization settings.

## Validation and logs

```bash
./scripts/vllm-model validate
./scripts/vllm-model logs
./scripts/vllm-model logs --gateway
./scripts/preflight_vllm_env.sh
```

Model logs are under `logs/models/`. Historical evidence remains under `test_results/`.

## Baseline

The known-good Qwen3-30B thinking profile remains unchanged. Print its exact command with:

```bash
./scripts/vllm-model show qwen3-30b-thinking-fp8
```

## Status meaning

Strict status policy: `PASS` requires evidence for the claimed capability on this exact host/config. Health, model listing, startup, or one non-empty response are not sufficient. `FAIL` means a required tested behavior failed; `NOT_TESTED` means it has not completed the acceptance harness. Historical artifacts remain under `test_results/` and are not deleted.

## Acceptance evidence

Use direct vLLM first, with embeddings stopped:

```bash
./scripts/vllm-evidence.py --context-tokens 8192
./scripts/vllm-evidence.py --context-tokens 16384
./scripts/vllm-evidence.py --context-tokens 32768 --stream
./scripts/vllm-evidence.py --context-tokens 8192 --tools
```

Each invocation saves raw JSON or SSE, usage, finish reason, leakage checks, latency, and GPU snapshots under a timestamped `test_results/vllm-evidence/` directory. A request ending with `finish_reason=length`, empty final content, leaked think tags, malformed/missing tool calls, or a broken stream is FAIL.


## Marco-DeepResearch-8B result

Status: `FAILED` for the current required chat behavior. The server reached `/health` and returned JSON, but the response exposed incomplete `<think>` content in `message.content` and ended with `finish_reason: length`; clean reasoning separation and a usable final answer were not confirmed.


## DR-Venus-4B-RL result

Status: `FAILED` for agentic RAG. The server and parser started, but the response contained repeated text, leaked `</think>` tags, and ended with `finish_reason: length`; no clean final answer was produced. Tool use is therefore not considered validated.


## Qwen2.5-32B-Instruct-AWQ result

Status: `FAILED` (user-reported). The exact failure output was not supplied, so no narrower failure class is claimed.


## DeepSeek-R1 Distill Qwen-32B AWQ result

Status: `FAILED` (user-reported). The exact failure output was not supplied, so no narrower failure class is claimed. Tool calling was not validated.


## Gemma-4 E4B-it result

Status: `FAILED` for chat generation. The server was queried with the configured Gemma parsers, but the basic chat request timed out after 180 seconds with zero response bytes.


## Recently verified

- `Qwen/Qwen3.6-27B-FP8`: `PASS` — user confirmed server load and chat response.
- `meta-llama/Llama-3.1-8B-Instruct`: `PASS` — user confirmed server load and chat response after license acceptance.


## Additional non-Qwen candidates

`CohereLabs/c4ai-command-r7b-12-2024` is configured as `cohere-command-r7b` with a 65,536-token starting context. It is designed for RAG and multi-step tool use, but requires accepting Cohere access conditions. Its older Command R7B tool format is not assigned a parser in vLLM 0.21 until a probe confirms the format.

Thinking Machines Lab `thinkingmachines/Inkling` is not added as runnable: `Inkling-Small` is listed at 266B parameters and `Inkling-Small-NVFP4` at 156B, so neither is practical on this 40GB A100.


## Context policy

Profiles now use the largest defensible context from cached checkpoint metadata: 65,536 where the model supports it, Qwen3-8B at its declared 40,960 maximum, and smaller values retained only for checkpoints with unverified or hard lower limits. Long context increases KV-cache memory and may require lowering `--gpu-memory-utilization` or `--max-num-seqs`.


Qwen3.8-27B INT8 MTP now targets 65,536 context with one sequence, 0.95 GPU utilization, and automatic KV-cache dtype. The 8,192-token command remains the last user-verified configuration; validate the expanded profile before relying on it.
