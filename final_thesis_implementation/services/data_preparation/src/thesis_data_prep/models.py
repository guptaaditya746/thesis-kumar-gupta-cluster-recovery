from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


ProcessorName = Literal[
    "bcplus_qa",
    "browsecomp_docs",
    "bright_docs",
    "publish_file",
    "publish_tree",
]


class RepositoryConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    repo_id: str
    repo_type: Literal["dataset", "model", "space"] = "dataset"
    raw_dir: str
    revision: str | None = None

    @field_validator("raw_dir")
    @classmethod
    def validate_raw_dir(cls, value: str) -> str:
        path = Path(value)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("raw_dir must stay inside the configured data root")
        return value


class ResourceConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["benchmark", "corpus"]
    repository: str
    allow_patterns: list[str] = Field(min_length=1)
    source: str
    output: str
    processor: ProcessorName
    description: str = ""
    large: bool = False
    expected_min_records: int | None = None
    expected_min_files: int | None = None
    options: dict[str, Any] = Field(default_factory=dict)

    @field_validator("source", "output")
    @classmethod
    def reject_absolute_paths(cls, value: str) -> str:
        path = Path(value)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("paths must stay inside their configured root")
        return value


class DatasetConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: str
    benchmark: str
    corpus: str
    aliases: list[str] = Field(default_factory=list)


class ServiceConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = 1
    workspace_root: str = "../.."
    data_root: str = "data"
    repositories: dict[str, RepositoryConfig]
    resources: dict[str, ResourceConfig]
    datasets: dict[str, DatasetConfig]
    groups: dict[str, list[str]] = Field(default_factory=dict)
