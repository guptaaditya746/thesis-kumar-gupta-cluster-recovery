# Service boundary

`query_driven` is one standalone thesis service representing the complete Query-Driven Multimodal GraphRAG method.

It owns:

- agentic full-corpus document retrieval through the sibling Pi runtime (`rg`/`read`/`bash`)

- graph-pattern generation
- graph-pattern-guided text relation/entity extraction
- local multimodal graph construction
- query-driven graph inference/refinement
- optional image/table augmentation
- final answer generation
- dataset-specific evaluation (QA exact match/token F1, BRIGHT retrieval metrics, and MMQA reproduction metrics)
- stage caches and run artifacts
- model/endpoints configuration
- structured logging

It does not import DCI. For open-corpus runs it independently invokes the existing sibling `services/pi_runtime/pi-mono` checkout; that upstream runtime is not modified.

## Design choices

1. **One service, not multiple services.** Internal Python modules mirror algorithmic stages only.
2. **Config-driven.** Paths, models, endpoints, concurrency, stage selection, cache roots, and optional multimodal components are TOML settings.
3. **`structlog`.** Human-readable colored console logs by default; JSON logs are selectable.
4. **Artifact-first.** Every stage writes explicit artifacts and can resume from them.
5. **Preserve upstream snapshot.** The supplied code stays under `upstream/` untouched.
6. **Retrieval boundary.** Corpus retrieval is agentic and filesystem-based; embeddings are reserved for local graph-node selection after extraction.
7. **Lazy heavy dependencies.** Torch/Transformers/Gemini are only required when the corresponding multimodal options are enabled.
8. **No embedded secrets.** Config stores environment-variable names, not credentials.

## Typical repository placement

```text
services/
  dci/
  pi_runtime/
  query_driven/
    config/
    src/query_driven/
    upstream/
    tests/
    pyproject.toml
```
