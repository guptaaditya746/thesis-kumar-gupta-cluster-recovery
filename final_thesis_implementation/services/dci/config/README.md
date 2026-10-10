# DCI configuration

All paths are resolved relative to `services/dci`, regardless of the config
file's directory.

```text
config/
├── single.toml
├── terminal.toml
├── answer_qa/
│   ├── 2wikimultihopqa.toml
│   ├── bamboogle.toml
│   ├── browsecomp_plus.toml
│   ├── hotpotqa.toml
│   ├── musique.toml
│   ├── nq.toml
│   └── triviaqa.toml
├── retrieval/
│   ├── bright_biology.toml
│   ├── bright_earth_science.toml
│   ├── bright_economics.toml
│   └── bright_robotics.toml
├── maintenance/
│   ├── download_corpus.toml
│   ├── download_dataset.toml
│   ├── export_bcplus.toml
│   ├── export_bright.toml
│   ├── extract_bcplus_qa.toml
│   └── print_system_prompt.toml
└── prompts/
    └── answer_qa.j2
```

## Environment

Model-provider and Langtrace credentials belong in `.env`, never in TOML.
Load them explicitly when invoking the service:

```bash
uv run --env-file .env dci-service --config CONFIG
```

If the editable environment is already synchronized and `uv` should not
rebuild it, add `--no-sync`:

```bash
uv run --no-sync --env-file .env dci-service --config CONFIG
```

## Active runs

Validate a config without launching Pi:

```bash
uv run --no-sync --env-file .env dci-service \
  --config config/retrieval/bright_biology.toml \
  --dry-run
```

Run BRIGHT retrieval:

```bash
uv run --no-sync --env-file .env dci-service \
  --config config/retrieval/bright_biology.toml
```

Run answer QA:

```bash
uv run --no-sync --env-file .env dci-service \
  --config config/answer_qa/bamboogle.toml
```

Launch the interactive Pi terminal:

```bash
uv run --no-sync --env-file .env dci-service \
  --config config/terminal.toml
```

## Maintenance

Files under `maintenance/` describe optional data download, conversion, and
inspection operations. Normal benchmark runs consume the prepared files under
`../../data/processed/` and do not require these operations.

Run maintenance operations with the same command form, for example:

```bash
uv run --no-sync --env-file .env dci-service \
  --config config/maintenance/print_system_prompt.toml
```
