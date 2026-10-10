from __future__ import annotations

from pathlib import Path

from thesis_data_prep.settings import load_config


def test_config_resolves_workspace_and_data_root(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    service = workspace / "services" / "data_preparation"
    config_dir = service / "configs"
    config_dir.mkdir(parents=True)
    config = config_dir / "datasets.yaml"
    config.write_text(
        """
schema_version: 1
workspace_root: ../..
data_root: data
repositories:
  repo:
    repo_id: org/repo
    raw_dir: raw/repo
resources:
  benchmark.example:
    kind: benchmark
    repository: repo
    allow_patterns: [data/**]
    source: data/example.jsonl
    output: processed/example.jsonl
    processor: publish_file
datasets:
  example:
    description: Example
    benchmark: benchmark.example
    corpus: benchmark.example
""".strip()
        + "\n",
        encoding="utf-8",
    )

    settings = load_config(config)

    assert settings.service_root == service.resolve()
    assert settings.workspace_root == workspace.resolve()
    assert settings.data_root == (workspace / "data").resolve()
