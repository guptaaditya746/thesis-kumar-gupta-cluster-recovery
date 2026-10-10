from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml

from thesis_data_prep.models import DatasetConfig, RepositoryConfig, ResourceConfig, ServiceConfig


@dataclass(frozen=True)
class ResolvedConfig:
    config_path: Path
    service_root: Path
    workspace_root: Path
    data_root: Path
    config: ServiceConfig

    def repository_root(self, repository_name: str) -> Path:
        repo = self.repository(repository_name)
        return self.data_root / repo.raw_dir

    def repository(self, repository_name: str) -> RepositoryConfig:
        try:
            return self.config.repositories[repository_name]
        except KeyError as exc:
            raise KeyError(f"Unknown repository: {repository_name}") from exc

    def resource(self, resource_name: str) -> ResourceConfig:
        try:
            return self.config.resources[resource_name]
        except KeyError as exc:
            raise KeyError(f"Unknown resource: {resource_name}") from exc

    def dataset(self, dataset_name: str) -> tuple[str, DatasetConfig]:
        normalized = dataset_name.strip().lower().replace("-", "_")
        for canonical, dataset in self.config.datasets.items():
            candidates = {canonical.lower(), *(alias.lower().replace("-", "_") for alias in dataset.aliases)}
            if normalized in candidates:
                return canonical, dataset
        raise KeyError(f"Unknown dataset: {dataset_name}")

    def resource_source(self, resource_name: str) -> Path:
        resource = self.resource(resource_name)
        return self.repository_root(resource.repository) / resource.source

    def resource_output(self, resource_name: str) -> Path:
        return self.data_root / self.resource(resource_name).output


def discover_config_path(explicit: Path | None = None) -> Path:
    if explicit is not None:
        return explicit.expanduser().resolve()

    env_path = os.environ.get("DATA_PREP_CONFIG")
    if env_path:
        return Path(env_path).expanduser().resolve()

    cwd_candidate = Path.cwd() / "configs" / "datasets.yaml"
    if cwd_candidate.exists():
        return cwd_candidate.resolve()

    package_candidate = Path(__file__).resolve().parents[2] / "configs" / "datasets.yaml"
    if package_candidate.exists():
        return package_candidate.resolve()

    raise FileNotFoundError(
        "Could not find configs/datasets.yaml. Run from the service directory or pass --config."
    )


def load_config(config_path: Path | None = None, data_root_override: Path | None = None) -> ResolvedConfig:
    resolved_path = discover_config_path(config_path)
    payload = yaml.safe_load(resolved_path.read_text(encoding="utf-8"))
    config = ServiceConfig.model_validate(payload)

    service_root = resolved_path.parent.parent.resolve()
    workspace_root = (service_root / config.workspace_root).resolve()
    data_root = (
        data_root_override.expanduser().resolve()
        if data_root_override is not None
        else (workspace_root / config.data_root).resolve()
    )

    return ResolvedConfig(
        config_path=resolved_path,
        service_root=service_root,
        workspace_root=workspace_root,
        data_root=data_root,
        config=config,
    )
