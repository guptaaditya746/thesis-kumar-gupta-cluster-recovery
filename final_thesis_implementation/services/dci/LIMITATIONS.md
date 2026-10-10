# Current limitations, assumptions, and improvement opportunities

This document describes the current thesis-facing DCI service, not the claims
of the upstream DCI-Agent project. It is a living engineering assessment of
the implementation under `services/dci` as of 2026-08-19.

The service is useful for controlled experiments, but it is not yet a
production-grade retrieval service. In particular, a zero process exit code
currently means that orchestration finished; it does not guarantee that agent
runs, judgments, or metrics succeeded.

## Priority summary

| Priority | Limitation | Current consequence | Improvement direction |
|---|---|---|---|
| P0 | Benchmark exit status does not represent benchmark success | A run with failed queries or failed judgments can exit `0`, and the facade logs `operation_completed` | Define failure thresholds and return nonzero when required queries or judgments fail |
| P0 | An output root is not bound to an immutable experiment identity | Successful query directories may be reused after the model, prompt, tools, corpus, or config changes | Compute a run fingerprint, store it with every result, and reject incompatible reuse |
| P0 | Write-capable tools are enabled in active benchmark configs | The agent can modify corpus files despite prompt instructions not to do so | Default benchmarks to read-only tools and enforce filesystem isolation |
| P1 | QA and IR evaluation depend on fragile model-output conventions | Valid work can be skipped or scored incorrectly because formatting differs | Use structured outputs with schema validation and deterministic parsers |
| P1 | Runs have a turn limit but no end-to-end deadline | A stuck provider, tool, or child process can hold a worker indefinitely | Add query, tool, provider, and benchmark deadlines with explicit timeout statuses |
| P1 | Configuration validation is partial | Typos in unknown keys are ignored and many missing paths fail only after launch | Introduce a strict typed schema and preflight validation |
| P1 | Reproducibility metadata is incomplete | Model aliases, external Pi code, provider state, prompts, and environment can drift between runs | Record immutable revisions, hashes, dependency versions, and endpoint metadata |
| P1 | Artifacts and traces can contain sensitive corpus content | Questions, responses, reasoning, commands, and tool results may be stored or exported | Add redaction, retention controls, access guidance, and explicit consent profiles |
| P2 | The benchmark evaluator is a large multi-purpose script | Orchestration, prompting, scoring, resumption, reporting, and plotting are tightly coupled | Split these responsibilities behind tested interfaces |
| P2 | Automated testing covers only a small part of the behavior | Integration failures across Python, Node, Pi, providers, and telemetry are detected during runs | Add fixture-based unit tests and hermetic end-to-end smoke tests |
| P2 | Legacy and thesis-facing documentation overlap | Users can follow commands and paths that do not match the current service layout | Mark legacy material clearly and make the facade guide the canonical entry point |

## Confirmed limitations

### 1. Completion and success are different states

The benchmark evaluator returns success after it finishes aggregation even when
individual agent runs or judgments failed. Consequently, `dci-service` reports
`operation_completed` whenever the evaluator process returns zero. This is why
an output such as `failed_judgments=50` can still end with service return code
zero.

This behavior is suitable only if downstream users always inspect
`summary.json`. It is unsafe for Slurm dependencies, CI jobs, shell pipelines,
and experiment automation that use process status as the success signal.

Improve it by:

- defining separate orchestration, run, evaluation, and quality statuses;
- adding policy flags such as `fail_on_run_error`, `fail_on_judge_error`, and
  minimum completion coverage;
- returning a nonzero code when the selected policy is violated;
- printing the artifact path and failure summary in the final service log.

### 2. Output-directory reuse can invalidate experiments

The evaluator identifies cached work primarily by `query_id` and existing
successful artifacts. It does not bind those artifacts to a hash of the active
model, provider, tools, prompt, corpus, dataset, Pi revision, and service
configuration. Reusing an output root after changing one of those inputs may
silently mix old and new query results.

Until this is fixed, treat every output root as immutable and unique to one
complete experimental configuration.

Improve it by computing a canonical experiment fingerprint before work starts,
writing it to the output root and each query result, and refusing to reuse a
directory whose fingerprint differs. An explicit migration or `--force-new`
path should be required to override the check.

### 3. Tool access is broader than the research contract

The active benchmark configs currently include `edit` and `write`, while the
benchmark prompts tell the agent not to modify corpus files. That restriction
is advisory: the tool permissions still allow mutation. The `bash` tool also
provides a broad execution surface and may read outside the intended corpus if
the runtime is not sandboxed.

Improve it by:

- making `read`, `grep`, `find`, and `ls` the default benchmark tool set;
- using a read-only corpus mount or sandbox rather than relying on prompting;
- restricting shell commands and accessible paths where possible;
- recording every allowed capability as part of the experiment identity.

### 4. QA evaluation is format- and judge-dependent

A QA answer is judged only when the agent run completed, produced non-empty
text, and included the literal marker `Exact Answer:`. A semantically correct
answer without that marker is recorded as an unjudged result. Correctness then
depends on an OpenAI-compatible model judge, its prompt behavior, endpoint
availability, timeout, and model alias.

The configured token prices are manual estimates rather than authoritative
provider billing, and a local endpoint may not report usage in the expected
shape.

Improve it by using a structured final-answer schema, validating it at the
runtime boundary, separating parse failure from agent failure, and measuring
judge agreement against a human-labeled sample. Exact-match or normalized
deterministic scoring should be preferred where the dataset permits it.

### 5. IR evaluation has a brittle text interface

The IR evaluator extracts a `Relevant Documents` block with a regular
expression. It then reduces paths to basenames. This creates several risks:

- harmless formatting changes can produce an empty ranking;
- documents with the same basename in different directories collide;
- path identity no longer represents the actual corpus hierarchy;
- duplicate retrieved paths are not explicitly deduplicated before NDCG;
- only binary membership in the gold set is represented;
- the hard-coded metric and response limit make broader IR evaluation awkward.

Improve it by requiring a JSON ranking containing stable document IDs,
validating IDs against a corpus manifest, deduplicating deterministically, and
moving metric calculation into a tested evaluation module. The metric cutoff
and relevance grades should be dataset configuration, not parser assumptions.

### 6. Configuration is permissive rather than strict

Configuration loading validates TOML syntax, version, operation, and fields
that a command builder happens to read. Unknown tables and misspelled keys are
silently ignored. `--dry-run` resolves a command but does not prove that all
input paths exist, the Pi build is compatible, credentials are present, model
aliases resolve, endpoints respond, or output locations are writable.

Improve it with a typed, operation-specific schema that rejects unknown keys
and validates ranges and cross-field constraints. Add a separate `preflight`
operation for filesystem, executable, credential-name, provider, endpoint, and
write-permission checks. Preflight must avoid sending secrets or running a full
query.

### 7. There is no complete timeout and cancellation model

`max_turns` limits model turns, and judge calls have an HTTP timeout, but the
benchmark worker waits for the query subprocess without an overall deadline.
A blocked model stream, shell command, Pi process, or child process can occupy
a worker indefinitely. Interrupting the parent also does not define a durable
cross-process cancellation protocol.

Improve it by defining time budgets at four levels: benchmark, query, model
request, and tool call. On expiration, terminate the entire process group,
persist a typed timeout result, close telemetry spans, and leave artifacts in a
safe resumable state.

### 8. Reproducibility depends on mutable external state

The service records resolved commands and substantial run metadata, but it is
coupled to a sibling Pi checkout, a Node installation, provider configuration,
environment variables, mutable model aliases, and external serving state. A
config stating `model = "qwen-chat"` does not identify model weights, serving
parameters, tokenizer, quantization, chat template, or backend revision.

Improve it by recording at least:

- Git revisions and dirty-state hashes for DCI and Pi;
- hashes of prompts, configs, datasets, and corpus manifests;
- Python, Node, package-lock, and environment versions;
- resolved provider/model metadata and inference parameters;
- Slurm job, host, GPU, and server revision information where available.

### 9. Telemetry is best-effort and incomplete by design

Langtrace initialization failures and RPC-event translation failures do not
fail a run. This is desirable for evaluation availability, but it means the
absence of a trace is not represented as an experiment failure. The current
custom bridge observes Pi RPC lifecycle events; it does not instrument the
Node provider call as a native Python OpenAI request. Terminal mode bypasses
the RPC artifact runner and therefore does not produce these query traces.

Content capture is disabled unless `LANGTRACE_CAPTURE_CONTENT=true`; when
enabled, individual exported content attributes are truncated at 32,000
characters. Batch export defaults to disabled, and trace delivery still
depends on network reachability and process shutdown behavior.

Improve it by recording telemetry status and trace ID in a structured run
manifest, adding export-health counters and flush confirmation, documenting
terminal-mode behavior, and testing the event bridge against pinned Pi event
fixtures. Keep content capture opt-in.

### 10. Artifact persistence trades speed for inspectability

The runner rewrites several JSON snapshots after events so progress can be
inspected while a query runs. Long, tool-heavy trajectories can therefore
generate substantial serialization and shared-filesystem I/O. Full
conversation artifacts, stderr, tool results, and optional traces can also
contain sensitive or very large content.

Improve it with configurable checkpoint intervals, append-oriented event
storage, bounded fields, compression, retention policies, and a final
compaction pass. Clearly distinguish authoritative raw events from derived
views that can be regenerated.

### 11. Concurrency assumes isolated ownership

In-process query concurrency is bounded by a semaphore, but there is no lock
preventing two service processes from writing the same output root. Workers
also share the provider endpoint, Pi installation, agent directory, corpus,
and filesystem. Increasing concurrency can change latency, timeout rates,
server batching, and therefore experimental behavior.

Improve it by acquiring an output-root lock, exposing resource-aware
concurrency controls, recording queue and server timing, and treating
concurrency as part of the experiment fingerprint.

### 12. The evaluator has weak module boundaries

`scripts/bcplus_eval/run_bcplus_eval.py` currently owns dataset loading,
prompt construction, process orchestration, cache/resume decisions, QA
judging, IR parsing and scoring, aggregation, reports, and plots. The RPC runner
also combines process control, recording, conversation transformation,
evaluation, and telemetry integration.

This makes changes difficult to test independently and increases the chance
that a reporting change affects execution semantics.

Improve it by separating domain modules for datasets, experiment identity,
trajectory execution, artifact storage, QA evaluation, IR evaluation,
aggregation, and reporting. Keep the CLI as composition code.

### 13. Test coverage is narrow

The repository currently contains focused tests for a few command-building
paths, QA prompt construction, and RPC-to-trace span translation. There are no
hermetic tests for benchmark success policy, output-root compatibility,
resumption, malformed datasets, IR parsing edge cases, process timeout,
concurrent writes, artifact recovery, or live Pi integration. The project also
does not declare `pytest`, despite that being a common invocation developers
may try; the existing tests are based on `unittest`.

Improve it with small fixture-driven tests for every state transition and
parser, followed by one fake-Pi integration test and one opt-in live smoke
test. Declare a development dependency group and one canonical test command.

### 14. Documentation has two historical layers

The root README and `assets/docs/` preserve upstream commands and defaults,
while `SERVICE.md` and `config/README.md` describe the thesis-facing sibling
layout and config-driven entry point. Some legacy paths and assumptions do not
match the current service deployment.

Improve it by marking every legacy page as such, linking all active workflows
through `SERVICE.md`, and generating CLI/config reference material from the
typed schema once one exists.

## Operating assumptions

The current service is reliable only when these assumptions hold:

1. The DCI service and compatible Pi checkout retain the expected sibling
   layout, or every Pi path is overridden correctly.
2. Node 20 or newer, the built Pi CLI, Python dependencies, and required Unix
   search tools are available on every execution node.
3. The corpus and dataset are trusted. In particular, `query_id` values are
   safe directory names and do not contain traversal components.
4. One benchmark process owns an output root, and the output root is used for
   only one immutable experimental configuration.
5. Corpus files are readable local text in a layout compatible with the prompt
   and scoring logic; document basenames are unique where IR scoring relies on
   them.
6. The model follows tool-use and final-response formatting instructions well
   enough for the evaluator's text parsers.
7. Provider and judge endpoints implement the expected OpenAI/Pi-compatible
   behavior and return usable event and token metadata.
8. Environment variables are loaded into both the facade and all child
   processes; credentials are never placed in committed TOML files.
9. The shared filesystem supports the atomic replace and append patterns used
   by artifacts, with adequate space and acceptable metadata performance.
10. A missing Langtrace export is acceptable for benchmark execution, and any
    content exported to Langtrace is permitted to leave the compute node.
11. Manually configured prices are acceptable estimates rather than billing
    truth.
12. Dataset labels and model-based judgments are sufficiently accurate for the
    thesis claim being measured.

## Recommended implementation order

### Phase 1: trustworthy experiment status

1. Add typed result statuses and configurable nonzero exit policy.
2. Add experiment fingerprints and reject incompatible output-root reuse.
3. Remove write-capable tools from default benchmark configs.
4. Validate and sanitize `query_id` before using it as a path.

### Phase 2: trustworthy evaluation

1. Replace QA and IR free-form parsing with validated structured outputs.
2. Move QA and IR scoring into independent tested modules.
3. Add deterministic evaluation where datasets support it.
4. Add run, judge, and telemetry coverage metrics to the summary.

### Phase 3: operational robustness

1. Add end-to-end deadlines and process-group cancellation.
2. Add strict config schemas and a real preflight command.
3. Lock output roots and make checkpoint frequency configurable.
4. Record complete reproducibility and telemetry manifests.

### Phase 4: maintainability

1. Split the benchmark evaluator and RPC runner into focused modules.
2. Add hermetic integration fixtures and a declared development environment.
3. Consolidate active documentation and label legacy material.

## Criteria for a trustworthy benchmark run

A future benchmark run should be considered trustworthy only when all of the
following are machine-verifiable:

- its complete experiment identity is immutable and recorded;
- every expected query has exactly one terminal status;
- failure and judgment coverage satisfy an explicit policy;
- the scorer consumes validated structured predictions;
- artifacts belong to the active configuration and were not silently reused;
- tool and filesystem permissions match the documented research contract;
- timeout, interruption, and resume behavior preserve auditable state;
- software, model, prompt, dataset, corpus, and serving revisions are recorded;
- telemetry presence or absence is visible rather than inferred from a UI;
- the process exit code agrees with the configured success policy.
