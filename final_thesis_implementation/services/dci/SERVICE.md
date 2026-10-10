# DCI service

This package provides the config-driven facade around the Pi coding-agent
runtime located at `../pi_runtime/pi-mono`.

## Setup

```bash
cd services/dci
uv sync
```

Store provider and Langtrace credentials in `.env`. Do not put credentials in
TOML files.

## Configuration

Ready-to-run configs live under:

- `config/answer_qa/` for answer benchmarks and LLM judging;
- `config/retrieval/` for BRIGHT retrieval and NDCG evaluation;
- `config/single.toml` for one recorded query;
- `config/terminal.toml` for the interactive Pi terminal;
- `config/maintenance/` for optional data preparation.

See `config/README.md` for the complete layout and commands.

## Run

Validate without launching Pi:

```bash
uv run --no-sync --env-file .env dci-service \
  --config config/retrieval/bright_biology.toml \
  --dry-run
```

Run a benchmark:

```bash
uv run --no-sync --env-file .env dci-service \
  --config config/retrieval/bright_biology.toml
```

Launch the terminal:

```bash
uv run --no-sync --env-file .env dci-service \
  --config config/terminal.toml
```

## Artifacts and logging

The facade uses `structlog`; set `logging.json = true` for JSON logs. Benchmark
and single-run artifacts include the resolved config, command, RPC events,
conversation state, final response, metrics, and Langtrace identifiers when
tracing is enabled.

The lower-level entry points remain available for debugging, but
`dci-service` is the preferred thesis-facing interface.

## Design documentation

- [CONTEXT.md](CONTEXT.md) defines the canonical domain language used by this
  service.
- [LIMITATIONS.md](LIMITATIONS.md) records current limitations, operating
  assumptions, risks, and prioritized improvement directions.
