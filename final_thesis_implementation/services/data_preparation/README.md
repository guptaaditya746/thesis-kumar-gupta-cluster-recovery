# Thesis Data Preparation Service

A standalone `uv` project for downloading, preprocessing, validating, and publishing the datasets used by DCI-style thesis experiments.

The service is intentionally isolated from model setup and experiment execution. It owns its Python environment and writes only under the configured data root.

## Intended installation location

Extract the package so the thesis workspace looks like this:

```text
final_thesis_implementation/
├── code_review/
├── config/
├── data/
├── llm_setup/
└── services/
    └── data_preparation/
```

From your workspace root:

```bash
mkdir -p services
unzip thesis_data_preparation_service.zip -d services
cd services/data_preparation
bash scripts/bootstrap.sh
```

The included configuration assumes exactly that layout. It resolves the managed data directory as:

```text
../../data
```

relative to the service directory. Use `--data-root` or edit `configs/datasets.yaml` when installing elsewhere.

## What it creates

```text
data/
├── raw/
│   ├── benchmarks/dci-bench/
│   └── corpora/dci-agent-corpus/
├── interim/
├── processed/
│   ├── benchmarks/
│   │   ├── browsecomp_plus/bcplus_qa.jsonl
│   │   ├── bright/
│   │   └── wiki_qa/
│   └── corpora/
│       ├── browsecomp_plus/
│       ├── bright/
│       └── wiki -> ../../raw/corpora/dci-agent-corpus/wiki
├── manifests/
│   ├── downloads/
│   └── datasets/
├── checksums/
└── logs/
```

`raw/` contains upstream downloads and should be treated as immutable. `processed/` contains the stable paths consumed by experiment code.

## Environment setup

Requirements:

- Python 3.10+
- `uv`
- enough storage for the selected corpora
- Hugging Face access for repositories that require authentication

```bash
cd services/data_preparation
uv sync --all-groups
# Commit the generated uv.lock to pin the resolved environment for thesis runs.
uv run data-prep init
uv run data-prep doctor
```

Authenticate when needed:

```bash
hf auth login
```

The `.venv/` directory belongs only to this service.

## Main commands

Show the dataset catalog:

```bash
uv run data-prep catalog
```

Show raw and processed status:

```bash
uv run data-prep status
```

Prepare BrowseComp-Plus end to end:

```bash
uv run data-prep prepare browsecomp_plus
```

Prepare all BRIGHT subsets using the configured group:

```bash
uv run data-prep prepare bright
```

Prepare one Wikipedia-backed QA dataset and the shared Wikipedia-18 corpus:

```bash
uv run data-prep prepare nq --include-large
```

Prepare all Wikipedia-backed QA datasets:

```bash
CONFIRM_WIKIPEDIA_DOWNLOAD=YES bash scripts/prepare_wikipedia_qa.sh
```

Wikipedia-18 contains millions of files. Check Ceph quota and inode limits before running that command.

## Reusing existing downloads

The Hugging Face client is idempotent and reuses files already present in `raw/`. Processing also skips outputs with valid completion markers.

To process already downloaded data without network access:

```bash
uv run data-prep prepare browsecomp_plus --no-download
```

To rebuild only processed outputs:

```bash
uv run data-prep prepare browsecomp_plus --no-download --force-process
```

To force Hugging Face to download selected files again:

```bash
uv run data-prep prepare browsecomp_plus --force-download
```

Use force flags carefully. The service never deletes raw downloads, but `--force-process` replaces the selected processed output.

## Validation and manifests

Validate prepared outputs:

```bash
uv run data-prep validate browsecomp_plus
uv run data-prep validate bright_biology bright_robotics
```

Regenerate dataset manifests:

```bash
uv run data-prep manifest browsecomp_plus
```

A dataset manifest records:

- source repository and paths
- processed output paths
- validation results
- file hashes for benchmark files
- bounded directory fingerprints for corpora
- Python, platform, hostname, and service version

Download markers under `data/manifests/downloads/` also record the resolved Hugging Face revision when available.

## Dataset aliases

Examples:

```bash
uv run data-prep prepare bcplus
uv run data-prep prepare bright-biology
uv run data-prep prepare natural-questions --include-large
uv run data-prep prepare 2wiki --include-large
```

Run `uv run data-prep catalog` for canonical names and groups. `all_small` prepares BrowseComp-Plus plus all BRIGHT subsets without selecting Wikipedia. `all` includes Wikipedia and therefore requires `--include-large`.

## Configuration

Edit `configs/datasets.yaml` to change repositories, revisions, paths, expected minimum counts, or add datasets.

Every resource defines:

```yaml
kind: benchmark | corpus
repository: benchmarks | corpora
allow_patterns: [...]
source: path/inside/raw/repository
output: path/inside/data/root
processor: bcplus_qa | browsecomp_docs | bright_docs | publish_file | publish_tree
```

Pin an upstream repository revision for reproducible thesis runs:

```yaml
repositories:
  benchmarks:
    repo_id: DCI-Agent/dci-bench
    repo_type: dataset
    raw_dir: raw/benchmarks/dci-bench
    revision: <commit-sha>
```

You can also override paths at runtime:

```bash
uv run data-prep \
  --config /path/to/datasets.yaml \
  --data-root /path/to/data \
  status
```

Environment equivalents:

```bash
export DATA_PREP_CONFIG=/path/to/datasets.yaml
export DATA_PREP_DATA_ROOT=/path/to/data
```

## Using the outputs from experiment code

Experiment services should consume only stable processed paths, for example:

```text
data/processed/benchmarks/browsecomp_plus/bcplus_qa.jsonl
data/processed/corpora/browsecomp_plus/
```

Do not import this package into the LLM runner. The boundary between services is the filesystem plus the JSON manifests.

## Tests and linting

```bash
uv run pytest
uv run ruff check .
```

## Operational properties

- Independent `uv` environment
- No model training or fine-tuning
- Atomic benchmark publication
- Completion markers for large corpus exports
- Refusal to accept suspicious partial corpus directories
- Zero-copy symlink publication for Wikipedia-18
- Explicit opt-in for large resources
- Configurable and repeatable paths
- No writes outside the configured data root
