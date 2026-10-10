# DCI Thesis Service

The DCI thesis service evaluates direct corpus interaction: a model-driven
agent investigates a local document collection with tools and produces either
an answer or a ranked document list. This glossary defines the language used
across service configuration, execution, artifacts, evaluation, and telemetry.

## Core research language

**Direct Corpus Interaction (DCI)**:
A retrieval paradigm in which an agent investigates corpus files directly
with tools instead of querying a precomputed retrieval index or search API.
_Avoid_: DCI search engine, vector retrieval

**Corpus**:
The bounded local document collection that is available to an agent for a
query.
_Avoid_: database, index, knowledge base when referring only to the files

**Query**:
The task or information need presented to the agent for one investigation.
_Avoid_: prompt when referring to the underlying benchmark question

**Trajectory**:
The complete sequence of model decisions, tool interactions, and observations
for one query.
_Avoid_: trace when referring to the research process rather than telemetry

**Turn**:
One model-led step within a trajectory, potentially containing reasoning,
tool calls, and a response.
_Avoid_: request, query

**Tool Call**:
One agent-initiated interaction with an allowed corpus or shell tool.
_Avoid_: retrieval when the action may read, search, list, or modify files

**Evidence**:
Corpus content observed during a trajectory and used to support the final
answer or ranking.
_Avoid_: result when referring to source material

## Execution language

**Service Facade**:
The thesis-facing entry point that turns a versioned service configuration
into one operation.
_Avoid_: agent, runtime

**Operation**:
A configured unit of service behavior, such as a single query, terminal
session, benchmark, or data-maintenance task.
_Avoid_: mode when referring to the top-level service choice

**Pi Runtime**:
The external coding-agent runtime that conducts a trajectory and emits its
lifecycle events.
_Avoid_: DCI service, model provider

**Provider**:
The model-access backend selected for a Pi runtime invocation.
_Avoid_: model

**Model Alias**:
The configured identifier that a provider resolves to the model serving an
agent or judge request.
_Avoid_: model version unless the identifier is immutable

**Single Run**:
One recorded query trajectory outside a benchmark batch.
_Avoid_: benchmark query

**Terminal Session**:
An interactive Pi runtime session controlled by a human.
_Avoid_: single run, benchmark run

**Benchmark Run**:
The evaluation of a fixed dataset against one configured agent and corpus
setup.
_Avoid_: experiment when the configuration identity has not been recorded

**Query Run**:
The trajectory and evaluation associated with one benchmark item.
_Avoid_: benchmark run

**Output Root**:
The directory that owns the aggregate and per-query artifacts for exactly one
benchmark configuration.
_Avoid_: run directory when referring to the whole benchmark

**Run Artifact**:
A durable record produced by a single run or query run, such as its question,
events, conversation, final response, status, or metrics.
_Avoid_: log when the record is structured experiment output

**RPC Event**:
A structured lifecycle observation emitted by the Pi runtime during a
trajectory.
_Avoid_: trace span

**Telemetry Trace**:
An observability representation of a trajectory composed of nested spans for
the query, turns, model activity, and tool activity.
_Avoid_: trajectory when referring only to exported observability data

## Context and continuity language

**Runtime Model Context**:
The message history and tool information prepared for the model's next
request.
_Avoid_: conversation artifact

**Runtime Context Management**:
Changes to the runtime model context intended to keep a long trajectory within
the model's context budget.
_Avoid_: artifact compaction

**Conversation View**:
A saved representation of a trajectory intended for inspection and analysis.
_Avoid_: runtime model context

**Artifact Compaction**:
Post-observation reduction or externalization of content in a saved
conversation view without changing what the model saw.
_Avoid_: runtime context management

**Resume**:
Continuation of an incomplete run using an existing artifact directory.
_Avoid_: rerun, retry

**Session Continuity**:
Preservation of the Pi runtime's model-session history across invocations.
_Avoid_: resume; artifact reuse alone does not imply session continuity

## Evaluation language

**QA Benchmark**:
A benchmark whose query runs produce answers that are compared with reference
answers.
_Avoid_: retrieval benchmark

**IR Benchmark**:
A benchmark whose query runs produce ranked corpus documents that are scored
for relevance and ordering.
_Avoid_: QA benchmark

**Gold Answer**:
The reference answer supplied by a QA dataset.
_Avoid_: correct answer when the reference may be incomplete or ambiguous

**Predicted Answer**:
The final answer produced by the agent for a query run.
_Avoid_: result when referring specifically to answer text

**Judge**:
The evaluator that decides whether a predicted answer is equivalent to a gold
answer.
_Avoid_: agent model, provider

**Judgment**:
The judge's correctness decision and supporting evaluation metadata for one
predicted answer.
_Avoid_: score when referring to the full evaluation record

**Gold Document**:
A corpus document marked relevant for an IR query by the dataset.
_Avoid_: retrieved document

**Retrieved Document**:
A corpus document included in the agent's final ranked list.
_Avoid_: gold document

**NDCG@10**:
The ranking metric that compares the first ten retrieved documents with the
dataset's gold-document relevance labels while rewarding relevant documents
that appear earlier.
_Avoid_: accuracy

## Data preparation language

**Raw Data**:
Downloaded source material retained before thesis-specific transformation.
_Avoid_: corpus when the data is not yet ready for agent use

**Processed Data**:
Dataset or corpus material transformed into the layout consumed by active
runs.
_Avoid_: raw data

**Maintenance Operation**:
A non-evaluation operation that downloads, extracts, exports, or inspects data
needed by active runs.
_Avoid_: benchmark
