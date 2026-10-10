# Assumptions, Limitations, and Improvement Paths

## Why this document exists

A pipeline can exit successfully while producing weak retrieval, an empty graph,
or a wrong answer. Therefore “the command ran” and “the method worked” are
different claims.

This document starts from the properties a trustworthy experiment needs, then
compares the current implementation with those properties. It describes the
current code, not an idealized future system.

## First-principles requirements

A trustworthy query-driven retrieval experiment needs six properties:

1. **Evidence integrity** — every claim entering the graph must be traceable to
   corpus text actually selected for that question.
2. **Information isolation** — benchmark labels must not influence retrieval or
   answering.
3. **Termination** — every question must have finite compute, tool, output, and
   wall-time bounds.
4. **Reproducibility** — reused artifacts must correspond to the same question,
   corpus, prompts, models, and configuration.
5. **Observability** — a failure to search, parse, extract, or answer must be
   distinguishable from a valid empty result.
6. **Metric validity** — the reported metric must measure the task the run
   claims to solve.

The current service addresses all six, but only evidence-reference validation
and gold-field isolation are relatively strong. Semantic evidence quality,
artifact invalidation, and structured-output reliability remain partial.

## Assumption register

| ID | Current assumption | Why it matters | How to remove or test it |
| --- | --- | --- | --- |
| A1 | Question IDs are present and unique after string conversion | Artifacts and predictions are keyed by ID | Validate uniqueness before running and reject safe-ID collisions |
| A2 | File document stems are unique across the corpus | File stems become document IDs | Use root-relative paths or explicit metadata IDs |
| A3 | JSONL is uncompressed, UTF-8, and has one object per physical line | Retrieval stores byte offsets and seeks directly | Add indexed compressed-corpus adapters or preprocess into the canonical format |
| A4 | The configured JSONL ID is a string/number and content is a string | The adapter validates those field types | Add a normalization adapter for nested or structured content |
| A5 | A JSONL record is no larger than `max_document_bytes` | Record loading must be bounded | Validate corpus statistics before a run and report rejected oversize records |
| A6 | Corpus contents do not change during a run | Saved byte offsets and fingerprints otherwise become stale | Lock/version the corpus and record a content digest in the run manifest |
| A7 | Lexical search can surface the evidence | Pi currently searches with ripgrep | Add BM25/hybrid retrieval and compare recall under equal budgets |
| A8 | The model follows XML/JSON and tuple delimiters | Parsers depend on exact output structure | Use constrained decoding or typed tool results with validation and retry |
| A9 | Pi, Node, ripgrep, the model server, and tool-call parser are compatible | Retrieval depends on all of them | Add a preflight command that verifies versions and one tool round-trip |
| A10 | Model context is sufficient for prompt, history, previews, and output | Overflow previously caused retrieval failure | Track input/output tokens and compact by policy before the hard limit |
| A11 | Configured concurrency fits CPU, memory, filesystem, and model capacity | Every question may launch a Pi process and corpus scans | Derive concurrency from measured capacity or use a central work queue |
| A12 | Exact match/token F1 or retrieval metrics represent task success | Different datasets need different notions of correctness | Declare metric semantics per dataset and add groundedness/citation checks |
| A13 | Temperature zero makes runs sufficiently repeatable | Tool choice and serving kernels may still vary | Run repeated trials and report variance and completion rate |
| A14 | English prompts and title conventions fit the corpus | Exact-title search expects a JSON-encoded title followed by a newline | Make title fields explicit or use field-aware indexing |

## Current guarantees

### Gold-field isolation

For BRIGHT and text QA, runtime question objects retain only the configured
question ID and question text. Gold files are reopened only during evaluation.
This prevents an accidental use of `answer`, `gold_ids`, or supporting facts
through ordinary question metadata.

This does not protect against a corpus that itself contains benchmark answers
or annotations. Corpus provenance remains an experimental responsibility.

### Reference validation

File references are constrained to `corpus_root`. JSONL references must match
the configured corpus file, byte offset, document ID, and content field. This
protects against path traversal, fabricated offsets, and loading the aggregate
JSONL file as one extraction document.

Reference validation proves identity, not relevance. The selected record may
still fail to support the question.

### Bounded retrieval

Tool count and search time are per question. Model output is capped, JSON event
streaming uses an essential mode, and the Python process runner applies a hard
deadline after a finalization grace period.

A tool may still consume substantial resources before it returns, and multiple
questions can consume those resources concurrently.

## High-priority limitations

### L1. LLM output parsing is brittle

Pattern and extraction parsing rely on delimiters such as `##`, `<|>`, and
`<|COMPLETE|>`. A plausible model answer with missing delimiters can be saved
as a successful extraction artifact while graph construction silently skips
most records.

Observed consequence: the generic smoke run loaded the correct JSONL record,
but malformed extraction separators produced one node, zero edges, and a wrong
answer.

Improvement:

- replace free-form extraction text with a typed JSON schema;
- validate entity and relationship records before writing “complete”;
- retry repairable formatting failures;
- mark exhausted failures explicitly instead of constructing an empty graph;
- report extraction parse rate per run.

Acceptance criterion: every completed extraction artifact parses without
discarding records, or carries a machine-readable failure status.

### L2. Retrieval completion is not retrieval sufficiency

The agent may inspect evidence for several hops and return only one record. The
service validates the final list but does not prove that every question hop has
support.

Improvement:

- maintain a candidate/evidence ledger outside model prose;
- require each selected document to cite the hop it supports;
- validate that multi-hop plans have evidence coverage before finalization;
- distinguish `complete`, `partial`, `empty`, `unfinalized`, and
  `failed` statuses.

Acceptance criterion: each final document is linked to a required subclaim, and
a multi-hop result cannot be “complete” while a required subclaim is uncovered.

### L3. Stage resume is not fully content-addressed

Retrieval caches include a corpus fingerprint. Pattern, extraction, graph, and
inference reuse is mainly based on artifact existence. Changing a prompt,
model, question text, upstream artifact, or relevant config can therefore reuse
stale downstream output.

The file-corpus fingerprint uses directory metadata and may not detect content
changes below the root.

Improvement:

- create one run manifest containing hashes of normalized config, prompts,
  model identifiers, question content, corpus snapshot, and code revision;
- include upstream artifact hashes in each stage key;
- invalidate transitively when an input changes.

Acceptance criterion: changing any semantic input creates a different artifact
key, while unchanged inputs resume without model calls.

### L4. Standalone QA stages do not reconstruct all dependencies

For retrieval-based QA, `operation = "extraction"` loads no selected corpus
documents by itself. Construction similarly relies on question metadata and
prior artifacts created in the same in-memory pipeline path. A stage command
may therefore run without reproducing the previous stage’s hand-off.

Improvement:

- define a persisted stage-input manifest per question;
- make every stage load its declared inputs from artifacts;
- reject missing dependencies instead of producing an empty result.

Acceptance criterion: running stages separately produces byte-equivalent inputs
to running the complete pipeline.

### L5. Empty or partial graphs are not fail-fast errors

Graph construction skips malformed records. Inference can then run on an empty
or tiny graph, and the process still exits with code zero.

Improvement:

- configure minimum extraction, node, edge, and evidence-coverage thresholds;
- expose per-question terminal status;
- make strict smoke/benchmark profiles fail when thresholds are not met.

Acceptance criterion: infrastructure success, partial method success, and
answer success are separate reported outcomes.

## Scalability limitations

### L6. Corpus work is repeated per question

Each question starts a Pi process and searches the corpus independently. For
`Q` questions and `S` scans per question, corpus read work is approximately
`O(Q × S)`. Increasing concurrency overlaps scans but does not remove them and
can increase filesystem pressure.

Improvement:

- build one reusable lexical or hybrid index per immutable corpus;
- expose search behind a small corpus-search interface;
- share the index across questions;
- cache normalized query results where scientifically appropriate.

Acceptance criterion: corpus ingestion is approximately one-time, and adding
questions does not multiply full-corpus scans.

### L7. Concurrency is a manual capacity guess

`runtime.concurrency` controls model work and retrieval processes without
separate limits for model requests, Pi processes, filesystem scans, and
embeddings. A value suitable for extraction may overload retrieval.

Improvement:

- use stage-specific concurrency;
- add queue depth, memory, and latency telemetry;
- provide conservative defaults for smoke and full runs.

### L8. Search previews are truncated

The JSONL search tool returns at most 1,000 content characters for agent
inspection and at most 12 results per call. Evidence later in a record may be
missed even though extraction can load the complete selected record.

Improvement:

- support bounded context windows around each lexical match;
- allow follow-up record reads by validated reference;
- make result and preview bounds configurable and observable.

### L9. File documents are not size-bounded

JSONL records have `max_document_bytes`; individual file documents are read in
full. A very large file can therefore consume memory and model context.

Improvement: apply one document-size policy to all corpus adapters and add
chunk-addressed references where whole-document extraction is inappropriate.

## Representation limitations

### L10. The graph loses relation direction and multiplicity

Construction uses `networkx.Graph`, an undirected simple graph. Opposite
relations and multiple distinct relation instances between the same nodes are
merged. This is weaker than the directed typed pattern generated earlier.

Improvement: use a directed multigraph or an explicit edge table with relation
type, direction, provenance, confidence, and extraction span.

### L11. Entity identity is string-based

Nodes are keyed by uppercased entity name plus model-produced type. Aliases,
spelling variants, type disagreement, and two real entities with the same name
are not resolved. Relationships emitted before matching entity declarations can
also create untyped duplicate nodes.

Improvement:

- normalize entities through a dedicated resolver;
- preserve mention spans and source records;
- merge only with an explainable rule and confidence;
- measure entity/edge precision on a labeled sample.

### L12. Evidence provenance is document-level

Nodes and edges store source document IDs, but not exact character spans,
quotes, extraction confidence, or model-call identity.

Improvement: preserve span-level evidence from extraction through graph and
final answer, enabling citation checks and error attribution.

### L13. File document IDs can collide

The file adapter uses `path.stem`. For example, `a/report.txt` and
`b/report.txt` both become `report`, causing artifact and dictionary
collisions.

Improvement: use the normalized relative path as the canonical ID or require an
explicit file manifest.

### L14. Filesystem-safe IDs can collide

Question/document IDs are normalized for filenames. Distinct raw IDs may map to
the same safe form.

Improvement: append a stable short hash and save an explicit raw-ID-to-artifact
mapping.

## Evaluation limitations

### L15. Retrieval and answer quality are separate

Good retrieval can still produce a bad graph or answer; a model can also answer
correctly from prior knowledge despite poor retrieval. A single final-answer
score cannot locate the failure.

Improvement: report a stage funnel:

```text
completion
-> retrieval reference validity
-> evidence recall
-> extraction parse rate
-> graph coverage
-> answer accuracy
-> citation/groundedness
```

### L16. Selected-question matching supports common ID names only

Evaluation filtering checks `id`, `qid`, and `query_id`, while the dataset
configuration allows other question field names.

Improvement: pass the configured question ID field into evaluation.

### L17. No uncertainty or repeated-run report

One run reports point estimates only. Agentic tool use and model serving may
vary even at temperature zero.

Improvement: run multiple seeds/repetitions and report mean, variance,
completion rate, timeout rate, and parse-failure rate.

### L18. Answer metrics do not test grounding

Exact match and token F1 measure textual agreement, not whether the answer is
supported by retrieved evidence.

Improvement: produce answer citations and evaluate citation precision/recall or
entailment against selected evidence.

## Operational and safety limitations

### L19. Overwrite recursively deletes the configured output root

When `overwrite = true` and `resume = false`, the pipeline removes the
complete output root before recreating it. A mistaken broad path is dangerous.

Improvement: reject filesystem roots, repository roots, and paths outside an
approved output base; write a run-specific child directory.

### L20. There is no complete environment preflight

Config validation checks paths and numeric bounds, but not endpoint health,
model availability, authentication, tool-call support, ripgrep, Node version,
or a Pi tool round-trip.

Improvement: add a `preflight` operation that verifies every external
dependency without starting a benchmark.

### L21. Observability is intentionally compact

Essential Pi events prevent huge logs and `ENOBUFS`, but reduce postmortem
detail. The stored retrieval raw text contains assistant final text, not a full
bounded trace of every tool result.

Improvement: persist a size-bounded normalized trace with tool name, arguments,
duration, result count, token usage, and terminal reason.

## Improvement order

The recommended order follows dependency, not convenience:

1. **Structured extraction and terminal statuses** — stop silent corruption.
2. **Persisted stage manifests and content-addressed resume** — make experiments
   reproducible and standalone operations real.
3. **Evidence ledger and hop-coverage validation** — make retrieval completion
   semantically meaningful.
4. **Shared indexed corpus search and stage-specific concurrency** — scale after
   correctness is observable.
5. **Directed provenance-rich graph representation** — preserve what extraction
   actually claims.
6. **Stage-funnel evaluation and repeated trials** — measure where quality is
   gained or lost.
7. **Environment preflight and output-path guards** — make operation safer.

## Minimum bar before a full benchmark

Before scaling from one question to a full dataset:

- the config dry-run resolves the intended files and endpoints;
- one file-corpus and one JSONL-corpus smoke run complete;
- every retrieval result has a terminal status and valid references;
- extraction parse rate is 100% for the smoke sample;
- graph summaries have plausible node/edge counts;
- predictions contain exactly the selected question IDs;
- evaluation count equals the selected question count;
- no gold field appears in pre-evaluation artifacts;
- corpus, config, prompt, model, and code versions are recorded;
- concurrency is increased only after measuring one-question resource use.

Until these conditions hold, a zero score or long runtime should be treated as a
diagnostic result, not a conclusion about the research method.
