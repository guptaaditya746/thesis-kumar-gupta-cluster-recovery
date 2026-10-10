from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = Field(default=8501, ge=1, le=65535)


class PreviewConfig(BaseModel):
    default_rows: int = Field(default=100, ge=1, le=5000)
    maximum_rows: int = Field(default=5000, ge=1, le=100000)
    maximum_text_characters: int = Field(default=20000, ge=1000)
    quality_sample_rows: int = Field(default=50000, ge=100)


class CatalogConfig(BaseModel):
    database: Path
    recursive: bool = True
    exact_count_max_bytes: int = Field(default=128 * 1024 * 1024, ge=0)
    max_files_per_dataset: int = Field(default=250000, ge=1)
    follow_symlinks: bool = False


class SearchConfig(BaseModel):
    timeout_seconds: int = Field(default=20, ge=1, le=300)
    maximum_matches: int = Field(default=200, ge=1, le=10000)
    maximum_matches_per_file: int = Field(default=5, ge=1, le=1000)


class SafetyConfig(BaseModel):
    read_only: bool = True
    allow_sample_download: bool = True
    allow_full_dataset_download: bool = False


class DatasetConfig(BaseModel):
    id: str
    name: str
    benchmark_path: Path | None = None
    corpus_path: Path | None = None
    description: str | None = None

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("dataset id cannot be empty")
        return cleaned


class DashboardConfig(BaseModel):
    service_root: Path
    config_path: Path
    processed_root: Path
    manifest_root: Path
    output_root: Path
    experiment_root: Path
    server: ServerConfig = Field(default_factory=ServerConfig)
    preview: PreviewConfig = Field(default_factory=PreviewConfig)
    catalog: CatalogConfig
    search: SearchConfig = Field(default_factory=SearchConfig)
    safety: SafetyConfig = Field(default_factory=SafetyConfig)
    datasets: list[DatasetConfig] = Field(default_factory=list)


ArtifactType = Literal["benchmark", "corpus", "other"]
