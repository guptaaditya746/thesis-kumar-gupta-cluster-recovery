# Thesis Data Observatory

A standalone, read-only Streamlit dashboard for inspecting the thesis project's
`data/processed/` tree and completed Pi Bench experiments. It remains isolated from data
preparation, LLM setup, Pi runtime, and experiment execution.

## Features

- Automatic discovery of `processed/benchmarks/*` and `processed/corpora/*`
- DuckDB metadata catalog
- Lazy previews for JSONL, gzipped JSONL, JSON, CSV, TSV, Parquet, text, and Markdown
- Bounded corpus search through `ripgrep`
- Sample-based missingness, duplicate, schema, and text-length diagnostics
- Manifest and provenance viewer
- Benchmark-to-corpus availability view
- Pi Bench run comparison across quality, reliability, latency, tokens, and tool errors
- Per-sample question, response, score, prompt, usage, and tool-trajectory drill-down
- Read-only path guards
- Catalog scan limits for very large corpora
- Separate `uv` environment and generated output directory

The dashboard never writes into `data/processed/`. Its database, validation
reports, and caches live under `outputs/data_dashboard/`.

## Drop-in location

Extract the archive under the thesis project's `services/` directory:

```text
final_thesis_implementation/
├── data/
├── outputs/
└── services/
    └── data_dashboard/
```

From the thesis root:

```bash
mkdir -p services
unzip data_dashboard.zip -d services
cd services/data_dashboard
bash scripts/bootstrap.sh
```

`bootstrap.sh` creates the service's `.venv`, installs dependencies, validates
configuration, and builds the initial catalog.

## Expected data layout

The default configuration expects:

```text
data/
├── manifests/
└── processed/
    ├── benchmarks/
    │   ├── browsecomp_plus/
    │   ├── bright/
    │   └── trec_rag/
    └── corpora/
        ├── browsecomp_plus/
        ├── bright/
        └── trec_rag/
```

Immediate directories are auto-discovered. Explicit dataset paths can instead
be declared in `config/dashboard.yaml`.

## Commands

```bash
uv run data-dashboard config-check
uv run data-dashboard catalog build
uv run data-dashboard catalog refresh
uv run data-dashboard status
uv run data-dashboard validate
uv run data-dashboard serve
```

From `services/pi_bench_uv_starter`, the same dashboard can be launched with:

```bash
uv run pi-bench dashboard
uv run pi-bench dashboard --ngrok
```

The ngrok form requires `NGROK_AUTHTOKEN` (or an ngrok token already saved in the user
configuration) and exposes benchmark artifacts through a public URL.

Run on another port:

```bash
uv run data-dashboard serve --host 0.0.0.0 --port 8502
```

## Access through SSH

On `webis3`, launch the dashboard:

```bash
cd services/data_dashboard
uv run data-dashboard serve
```

On your local machine, open a tunnel:

```bash
ssh -L 8501:localhost:8501 xepi3167@webis3
```

Then visit:

```text
http://localhost:8501
```

## Large-corpus behavior

The catalog records metadata, not complete document contents. It avoids loading
whole datasets and limits the number of files cataloged per artifact using:

```yaml
catalog:
  max_files_per_dataset: 250000
```

For a corpus with millions of files, increase the limit only after checking
filesystem impact. Prefer sharded JSONL or Parquet over millions of tiny files.

Record counts are exact for Parquet metadata and for smaller line-oriented
files. Large JSONL/CSV files may show an unknown count until separately indexed.

## Configuration

Edit `config/dashboard.yaml` to change paths, ports, preview limits, scan limits,
the `experiment_root`, and explicit dataset mappings.

Example:

```yaml
datasets:
  - id: browsecomp_plus
    name: BrowseComp-Plus
    benchmark_path: ../../data/processed/benchmarks/browsecomp_plus
    corpus_path: ../../data/processed/corpora/browsecomp_plus
```

## Safety

- All browsed paths are checked against configured data roots.
- Search commands are executed without a shell.
- No delete, rename, edit, upload, or reprocess operation is exposed.
- Full-dataset downloads are disabled.
- Sample downloads can be disabled in configuration.

## Development

```bash
uv sync --all-extras
uv run pytest
uv run ruff check .
```
