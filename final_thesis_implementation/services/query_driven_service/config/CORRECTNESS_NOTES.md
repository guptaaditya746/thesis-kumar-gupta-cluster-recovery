# Query-Driven configuration pack

This pack separates two different experimental goals.

## 1. Reproduction

`config/reproduction/mmqa.toml`
`config/reproduction/webqa.toml`

These configs are for reproducing the original Query-Driven Multimodal GraphRAG
setting. The original code was designed around MMQA/WebQA data semantics and
answer evaluation.

## 2. Fair BRIGHT adaptation

`config/bright/*.toml`

These configs define the fair BRIGHT protocol:

```text
question
  -> query pattern
  -> retrieve from the FULL corpus
  -> retrieved_ids
  -> extraction on retrieved documents only
  -> graph construction
  -> inference
  -> answer

retrieved_ids + gold_ids
  -> retrieval evaluator
  -> NDCG@10 / Recall@K / MRR
```

`gold_ids` MUST NOT cross into pattern generation, retrieval, extraction, graph
construction, or inference.

## Problems in the last BRIGHT config

### Problem 1: `format = "webqa"`

BRIGHT is not WebQA. This was a compatibility workaround and can silently select
the wrong loader/evaluator behavior.

Correct direction:

```toml
[dataset]
format = "bright"
```

and implement explicit BRIGHT loading in the service.

### Problem 2: old evaluator

The existing standalone service evaluator was adapted from the original MMQA
list-answer evaluation. It computes list EM/F1. BRIGHT answers are long
free-form answers, so this is not the right primary metric.

Correct direction:

```toml
[evaluation]
kind = "retrieval"
gold_field = "gold_ids"
prediction_field = "retrieved_ids"
metrics = ["ndcg@10", "recall@10", "recall@20", "mrr"]
evaluate_answer = false
```

### Problem 3: using `gold_ids` as evidence

This is the most serious issue. If gold document IDs select the documents that
are fed to extraction/graph construction, the system receives the benchmark's
reference evidence. Retrieval is then not being evaluated fairly.

Correct direction:

- pipeline input: only `id`, `query`, and access to the full corpus;
- retrieval output: `retrieved_ids`;
- extraction consumes documents selected by `retrieved_ids`;
- evaluator alone reads `gold_ids`.

### Problem 4: no explicit retrieval stage

The original Query-Driven repository assumes dataset-provided supporting
documents in its MMQA workflow. For BRIGHT, a retrieval stage has to be added
before extraction.

Correct BRIGHT stage order:

```text
pattern -> retrieval -> extraction -> construct -> inference -> evaluation
```

### Problem 5: comment/config inconsistency

The last config said the loader accepted only a JSONL text index while also
setting `corpus_root`. Keep only one supported contract. For BRIGHT the cleaner
contract is a corpus directory:

```toml
corpus_root = "../../../data/processed/corpora/bright/biology"
```

The service should index/read that directory itself.

## Important implementation note

The BRIGHT configs are the TARGET contract. The service code must explicitly
support:

- `dataset.format = "bright"`
- `dataset.corpus_root`
- a retrieval stage
- `[retrieval]`
- retrieval evaluation via `retrieved_ids` and `gold_ids`

If the current local service does not consume these fields yet, config changes
alone are not sufficient. Do not silently fall back to WebQA/MMQA behavior.


## Text QA configs

The `config/qa/` family uses the same Query-Driven pipeline, but evaluates the
final answer instead of document ranking:

```text
question
  -> pattern
  -> retrieval over full Wiki corpus
  -> extraction
  -> graph
  -> inference
  -> predicted answer

predicted answer + gold answer
  -> exact match / token F1
```

Gold answers and supporting-fact/reference fields must not be used by retrieval
or graph construction.

Like the BRIGHT configs, these are target contracts. The service implementation
must explicitly support `dataset.format = "qa"`, the retrieval stage, and
`evaluation.kind = "answer_qa"` rather than silently reusing MMQA list scoring.
