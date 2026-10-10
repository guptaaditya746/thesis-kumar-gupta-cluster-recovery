# Architecture

## Purpose

The Query-Driven GraphRAG service answers or evaluates questions against a local
corpus. It converts each question into a query-specific graph pattern, retrieves
evidence, extracts matching entities and relationships, constructs an evidence
graph, performs iterative graph-based inference, and evaluates the result.

The service is an experiment runner rather than a general document database or
online API. TOML configuration defines one reproducible run.

## Supported problem families

| Dataset family | Evidence source | Primary output | Primary evaluation |
| --- | --- | --- | --- |
| MMQA/WebQA reproduction | Dataset-provided text, table, and image records | Answer | Original answer metrics |
| BRIGHT | Full directory of text files | Ranked document IDs | NDCG, recall, MRR |
| Text QA | Full file or JSONL corpus | Answer | Exact match, token F1 |

“Generic dataset support” means a dataset can be used when it satisfies one of
the documented input and corpus contracts. It does not mean arbitrary file
formats can be loaded without configuration or an adapter.

## End-to-end flow

```text
questions + TOML
       |
       v
  pattern generation
       |
       v
 agentic retrieval --------> validated document references
       |                              |
       |                              v
       +----------------------> exact document loading
                                      |
                                      v
                              entity/relation extraction
                                      |
                                      v
                              evidence graph construction
                                      |
                                      v
                              iterative graph inference
                                      |
                                      v
                              predictions + evaluation
```

For MMQA/WebQA reproduction, retrieval may be replaced by dataset-provided
document IDs. For BRIGHT and text QA, the complete sequence is:

```text
pattern -> retrieval -> extraction -> construct -> inference -> evaluate
```

Selecting `runtime.operation = "retrieval"` still runs pattern generation
first because the query pattern is an input to retrieval.

## Correctness invariants

The implementation is intended to preserve these invariants:

1. **No gold leakage.** Gold answers, gold documents, and supporting-fact fields
   are removed before pattern generation, retrieval, extraction, construction,
   and inference. The evaluator reopens the gold file separately.
2. **Validated evidence identity.** A final retrieval item must resolve to an
   existing file or to one exact JSONL record whose byte offset and document ID
   agree.
3. **Question-local budgets.** Search tool and time budgets apply independently
   to each question, not once to the complete run.
4. **Bounded finalization.** Exhausting the search budget blocks more tools but
   leaves a grace period for the model to emit its final retrieval block.
5. **No implicit candidate promotion.** If the agent does not emit a valid
   `<retrieval_result>`, inspected candidates are not silently treated as a
   successful result.
6. **Evaluation isolation.** Only question IDs selected for the run are scored.

These are implementation goals, not proofs of semantic correctness. In
particular, a valid document reference can still be irrelevant or insufficient.

## Stage contracts

| Stage | Reads | Writes | Important failure mode |
| --- | --- | --- | --- |
| Pattern | Question text | `pattern/<qid>.json` | Model output does not match the delimiter format |
| Retrieval | Question, pattern, corpus | `retrieval/<qid>/retrieval.json`, raw text, ranked IDs | Agent fails to finalize, times out, or returns invalid references |
| Extraction | Pattern and selected document text | `extraction/<qid>/<doc-id>.json` | Model emits malformed entity/relation tuples |
| Construct | Extraction artifacts, optional table/image metadata | GraphML and graph summary | Malformed tuples are skipped, producing a partial or empty graph |
| Inference | Graph, question, model and embedding endpoints | `inference/<qid>.json`, predictions | Graph lacks the evidence needed to answer |
| Evaluate | Predictions and gold file | `evaluation.json` | Prediction IDs or metric contract do not match the dataset |

## Corpus seam

The corpus seam is defined by `CorpusAdapter` in
`src/query_driven/corpus.py`. Its interface resolves an untrusted retrieval
reference into a trusted `CorpusDocument`.

### File corpus adapter

A file corpus uses one UTF-8 text file per document.

```toml
[dataset]
corpus_format = "files"
corpus_root = "/path/to/corpus"
```

The retrieval agent returns a path relative to `corpus_root`. The adapter
rejects paths outside the root and derives the document ID from the file stem.

### JSONL corpus adapter

A JSONL corpus uses one JSON object per physical line.

```toml
[dataset]
corpus_format = "jsonl"
corpus_root = "/path/to/corpus"
corpus_file = "documents.jsonl"
document_id_field = "doc_key"
document_content_field = "body"
max_document_bytes = 4194304
```

The retrieval agent returns:

```json
{
  "kind": "jsonl_record",
  "path": "documents.jsonl",
  "byte_offset": 12345,
  "document_id": "record-42"
}
```

The adapter seeks directly to the byte offset, reads one bounded line, parses
the object, verifies the configured ID field, and returns only the configured
content field. The complete aggregate corpus is never passed to extraction.

The tiny non-Wiki example is
`config/smoke/generic-jsonl-qa.toml`.

## Retrieval execution

Each question starts one Pi coding-agent process in the corpus directory. The
custom extension:

- exposes a bounded `search_jsonl` tool for aggregate JSONL corpora;
- caps model output tokens;
- blocks write/edit tools;
- blocks duplicate calls;
- enforces per-question tool and soft-time budgets;
- returns compact previews rather than the complete Pi event stream.

The Python runner drains stdout and stderr concurrently, uses a hard deadline
equal to search time plus finalization grace, and terminates the complete
process group on timeout.

Retrieval is lexical and agent-directed. It does not currently build a shared
BM25, vector, or hybrid index.

## Artifact model and resume behavior

Every run writes the resolved config and a copy of the input TOML. Question
artifacts are keyed by a filesystem-safe form of the question ID.

```text
<output_root>/
├── service-config.toml
├── resolved-config.json
├── pattern/<qid>.json
├── retrieval/<qid>/retrieval.json
├── retrieval/<qid>/retrieval_raw.txt
├── extraction/<qid>/<document-id>.json
├── graph/<qid>.graphml
├── graph/<qid>.summary.json
├── inference/<qid>.json
├── predictions.json
└── evaluation.json
```

Retrieval caches include a corpus fingerprint. Other stage artifacts are
currently reused mainly by file existence, so the limitations document should
be read before relying on resume for scientific reproducibility.

## Module map

| Module | Responsibility |
| --- | --- |
| `cli.py` | Load configuration, configure logging, run one operation |
| `config.py` | Typed configuration, relative path resolution, validation |
| `pipeline.py` | Stage ordering, input isolation, artifact hand-off |
| `pattern.py` | Query-specific graph-pattern generation and parsing |
| `retrieval.py` | Pi lifecycle, prompt, result parsing, retrieval artifacts |
| `corpus.py` | Trusted loading of file and JSONL document references |
| `extraction.py` | Entity/relation extraction from selected evidence |
| `graph.py` | Evidence graph construction and GraphML serialization |
| `inference.py` | Seed selection, graph expansion, answer generation |
| `evaluation.py` | MMQA, answer-QA, and retrieval metrics |
| `clients.py` | Text, embedding, vision, and image-selection model clients |
| `pi_extensions/retrieval-budget.mjs` | Pi tools and search-resource limits |

## Adding a dataset

A new dataset does not require code when it fits an existing contract:

1. Normalize questions to JSON or JSONL objects.
2. Choose stable, unique question and document IDs.
3. Choose `format = "qa"` or `format = "bright"`.
4. Choose `corpus_format = "files"` or `"jsonl"`.
5. Configure question, answer, document ID, and content field names.
6. Choose an evaluation kind whose metric semantics match the task.
7. Start with one question and `concurrency = 1`.
8. Inspect pattern, retrieval, extraction, graph summary, inference, and
   evaluation artifacts before scaling up.

A new corpus representation requires a new adapter at the corpus seam. A new
task metric requires a new evaluator contract; it should not be approximated by
reusing an unrelated metric.

## Operational entry points

Validate without executing models:

```bash
uv run query-driven --config config/smoke/generic-jsonl-qa.toml --dry-run
```

Run the self-contained one-question pipeline:

```bash
uv run query-driven --config config/smoke/generic-jsonl-qa.toml
```

Run a full benchmark only after the smoke artifacts are valid:

```bash
uv run query-driven --config config/qa/2wikimultihopqa.toml
```

See [Assumptions and limitations](ASSUMPTIONS_AND_LIMITATIONS.md) before
interpreting runtime or benchmark scores.
