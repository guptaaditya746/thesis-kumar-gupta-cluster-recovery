# Query-Driven configuration pack

```text
config/
├── bright/          # full BRIGHT retrieval benchmarks
├── qa/              # full answer-QA benchmarks
├── reproduction/    # original MMQA and WebQA experiments
├── smoke/           # one-question debugging runs
├── examples/        # generic templates
├── README.md
└── CORRECTNESS_NOTES.md
```

Families:

- `bright/`: canonical full BRIGHT retrieval-evaluation runs.
- `qa/`: canonical full Wiki-based answer-QA runs.
- `reproduction/`: original MMQA/WebQA-style experiments.
- `smoke/`: bounded one-question runs for validating infrastructure and pipeline changes.
- `examples/`: generic templates, not benchmark run definitions.

Data availability: `bright/robotics.toml` and the `reproduction/` configs require datasets that are not currently present under `data/processed`; they remain as explicit experiment templates.

Validate any config before running it:

```bash
uv run query-driven --config config/smoke/qa-2wikimultihopqa.toml --dry-run
```

See `CORRECTNESS_NOTES.md`.

## Corpus storage

BRIGHT corpora use one file per document and therefore keep the defaults:

```toml
corpus_format = "files"
```

Wiki QA uses one JSONL record per document inside a large aggregate file:

```toml
corpus_format = "jsonl"
corpus_file = "wiki_dump.jsonl"
document_id_field = "id"
document_content_field = "contents"
```
The JSONL schema is configurable; it is not required to use Wiki field names.
Set `document_id_field` and `document_content_field` to the fields used by the
corpus. `config/smoke/generic-jsonl-qa.toml` is a tiny self-contained example.


For JSONL corpora, Pi returns a record ID and byte offset. The service seeks to
that offset, verifies the ID, and sends only that record's content to
extraction. Cached retrieval artifacts include a corpus fingerprint and are
discarded when the aggregate file changes.

## Per-question search budget

```toml
[retrieval]
max_search_turns = 20
max_search_seconds = 270
finalization_grace_seconds = 30
```

The Pi extension blocks additional tools after the tool or soft-time budget,
then leaves the model a final answer turn. The process is terminated only after
the additional finalization grace period. An agent that never emits a final
`<retrieval_result>` is recorded as `unfinalized`; inspected candidates are not
promoted into successful retrieval results.
