# Codex Handoff: DCI BRIGHT Biology Run

## Current status

- Repository: services/dci
- Latest commit: 4d7090e (dci: reduce streaming event persistence pressure)
- Parent worktree is intentionally dirty; do not clean or reset unrelated changes.
- A one-sample BRIGHT biology run was launched with max-concurrency=1 and limit=1. At the last checkpoint it was still running after more than five minutes, with no ENOBUFS crash observed.

## Original failure

The BRIGHT biology run with max-concurrency=2 failed on qid=3 because the Node RPC process crashed with write ENOBUFS. qid=3 generated a huge rg tool command and produced 1,415 message/tool-call delta events. qid=0 and qid=1 also showed very slow bash searches. Reducing concurrency alone did not address per-agent event flooding.

## Implemented fix

File: src/dci/benchmark/pi_rpc_runner.py

- Streaming events message_update, toolcall_delta, and tool_execution_update are not persisted by default.
- These events are still consumed for live output and state accounting.
- Structural events, tool boundaries, final messages, and final artifacts remain persisted.
- Added --persist-stream-events as an opt-in flag for full raw streaming-event persistence.
- py_compile and CLI --help checks passed.

## Smoke-test command

Run from services/dci:

uv run python scripts/bcplus_eval/run_bcplus_eval.py --dataset ../../data/processed/benchmarks/bright/biology.jsonl --output-root ../../outputs/dci/bright/biology_one --corpus-dir ../../data/processed/corpora/bright/biology --package-dir ../pi_runtime/pi-mono/packages/coding-agent --agent-dir ../pi_runtime/pi-mono/.pi/agent --provider vllm --model qwen-chat --tools read,bash --max-turns 300 --runtime-context-level level3 --pi-thinking-level high --node-max-old-space-size 8192 --enable-ir --max-concurrency 1 --limit 1 --judge-model qwen-chat --judge-api-key-env VLLM_API_KEY

## Next steps

1. Check whether the running smoke test finished: outputs/dci/bright/biology_one/summary.json and outputs/dci/bright/biology_one/0/result.json.
2. Check events.jsonl size and event types; message_update/toolcall_delta/tool_execution_update should be absent by default.
3. If the run still hangs, inspect the last event and the generated shell command. The remaining issue may be slow broad corpus searches rather than RPC buffering.
4. Do not use --persist-stream-events for normal benchmark runs unless full streaming traces are specifically required.

## Important caution

The DCI directory was untracked in the parent repository, so commit 4d7090e added the full services/dci directory. The parent repository also contains unrelated dirty changes; preserve them.
