# Query-Driven Multimodal GraphRAG Service

Standalone, config-driven packaging of the Query-Driven Multimodal GraphRAG code supplied for the thesis implementation.

## Documentation

- [Architecture](docs/ARCHITECTURE.md) — runtime flow, stage contracts, corpus adapters, artifacts, and dataset integration.
- [Assumptions and limitations](docs/ASSUMPTIONS_AND_LIMITATIONS.md) — first-principles correctness requirements, known weaknesses, and a prioritized improvement roadmap.
- [Configuration guide](config/README.md) — config families and corpus settings.

The upstream repository describes the Query-Driven execution order as:

```text
pattern -> extraction -> construct -> inference -> evaluate
```

This service keeps that method as one application and replaces hard-coded paths/endpoints with a TOML configuration.

## Quick start

```bash
cd services/query_driven_service
uv sync
uv run query-driven --config config/smoke/qa-2wikimultihopqa.toml --dry-run
uv run query-driven --config config/smoke/qa-2wikimultihopqa.toml
```

Configuration families are documented in `config/README.md`. Use `smoke/` for quick checks and `bright/` or `qa/` for full benchmark runs.

For the optional CLIP/Gemini/image stack:

```bash
uv sync --extra multimodal
```

## Config-driven operations

Set `runtime.operation` in TOML to one of:

- `pipeline` - pattern, extraction, graph construction, inference, evaluation
- `pattern`
- `extraction`
- `construct`
- `inference`
- `retrieval` - agentic document discovery only
- `evaluate`

The CLI intentionally stays small. Normal experiments should change TOML, not grow long launch commands.

## Output layout

```text
outputs/mmqa/
  service-config.toml
  resolved-config.json
  pattern/<qid>.json
  extraction/<qid>/<document-id>.json
  graph/<qid>.graphml
  graph/<qid>.summary.json
  inference/<qid>.json
  predictions.json
  evaluation.json
```

Existing artifacts are reused when `runtime.resume = true` and `runtime.overwrite = false`.

## Models

The text model supports:

- OpenAI-compatible chat-completions endpoints
- Ollama-style generate endpoints

The optional embedding endpoint is used only by Query-Driven inference for local graph-node/entity selection. Agentic corpus retrieval uses the existing Pi runtime with filesystem tools and never builds a vector index. The optional image VLM, Gemini selector, and CLIP image preselector are configured separately.

Secrets are referenced through environment-variable names. Do not put API keys in TOML.

## Upstream snapshot

`upstream/` contains the exact files extracted from the provided Repomix snapshot. They are retained for comparison/provenance and are not imported by the runnable service.

The runnable `src/query_driven/` layer is intentionally separate because the supplied snapshot contains hard-coded/empty paths and endpoints, a missing `EXTRACT_RELATION_PROMPT` definition, an invalid assignment in `construct.py`, and imports that do not match the included files. The service reconstructs the contracts required to run the published stage sequence without silently editing the preserved snapshot.
