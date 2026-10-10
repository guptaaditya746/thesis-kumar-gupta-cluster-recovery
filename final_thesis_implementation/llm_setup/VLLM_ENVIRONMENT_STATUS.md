# vLLM Environment Status

This gate was run before any new-model load test. The virtual environment and dependency files were not recreated or modified.

| Check | Result |
| --- | --- |
| Python environment | PASS — Python 3.13.9 from `llm_setup/.venv` |
| vLLM import | PASS — vLLM 0.21.0 |
| PyTorch CUDA | PASS — PyTorch 2.11.0+cu130, CUDA available |
| GPU detected | PASS — 1 × NVIDIA A100-SXM4-40GB, capability 8.0, 40,960 MiB |
| Baseline server health | PASS — `/health` returned HTTP 200 |
| Baseline model listed | PASS — `/v1/models` listed `qwen-chat` rooted at `Qwen/Qwen3-30B-A3B-Thinking-2507-FP8` |
| Baseline chat response | PASS at API/HTTP level — valid completion returned; exact `MODEL_OK` content was not produced because the 32-token budget was consumed by reasoning |
| `nvcc` available | FAIL — `CUDA_HOME=UNSET`; `nvcc` was not found |
| Overall environment status | **ENVIRONMENT_PASS** |

The overall status follows the requested gate: imports succeeded, PyTorch saw the A100, the unchanged baseline reached `/health`, `/v1/models` worked, and a chat completion was returned. Missing `nvcc` is recorded as a toolkit diagnostic, not treated as a global blocker because the baseline loaded and served successfully.

## Evidence

- Static diagnostics: [`test_results/environment/preflight.txt`](test_results/environment/preflight.txt)
- Import assertion: [`test_results/environment/import_test.txt`](test_results/environment/import_test.txt)
- Baseline startup log: [`test_results/environment/baseline/startup.log`](test_results/environment/baseline/startup.log)
- Baseline health response: [`test_results/environment/baseline/health_response.txt`](test_results/environment/baseline/health_response.txt)
- Baseline model-list response: [`test_results/environment/baseline/models_response.json`](test_results/environment/baseline/models_response.json)
- Baseline chat response: [`test_results/environment/baseline/chat_response.json`](test_results/environment/baseline/chat_response.json)

The baseline used the supplied command unchanged, including 65,536 context, 0.95 GPU utilization, `deepseek_r1`, `hermes`, `TRITON_ATTN`, eager execution, prefix caching, and `VLLM_USE_FLASHINFER_SAMPLER=0`. Peak observed GPU allocation after loading was 39,005 MiB used and 1,437 MiB free. The server was stopped afterward and GPU usage returned to 0 MiB.

The four research questions remain separate:

1. Server compatibility: PASS for this baseline.
2. Tool protocol compatibility: not tested by this gate.
3. Agent capability: not tested by this gate.
4. Benchmark quality: not tested by this gate.
