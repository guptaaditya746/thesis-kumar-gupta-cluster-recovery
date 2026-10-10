from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from data_dashboard.models import DashboardConfig

SERVICE_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = SERVICE_ROOT / "config" / "dashboard.yaml"


def _resolve(base: Path, value: str | Path) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = base / path
    return path.resolve(strict=False)


def load_config(config_path: str | Path | None = None) -> DashboardConfig:
    selected = (
        Path(config_path or os.environ.get("DATA_DASHBOARD_CONFIG", DEFAULT_CONFIG))
        .expanduser()
        .resolve(strict=False)
    )
    if not selected.exists():
        raise FileNotFoundError(f"Dashboard configuration not found: {selected}")

    raw: dict[str, Any] = yaml.safe_load(selected.read_text(encoding="utf-8")) or {}
    service_root = selected.parent.parent.resolve()

    for key in ("processed_root", "manifest_root", "output_root"):
        if key not in raw:
            raise ValueError(f"Missing required configuration key: {key}")
        raw[key] = _resolve(service_root, raw[key])

    raw["experiment_root"] = _resolve(
        service_root,
        raw.get("experiment_root", "../../outputs/pi_bench/runs"),
    )

    catalog = dict(raw.get("catalog") or {})
    database_value = catalog.get("database", raw["output_root"] / "catalog.duckdb")
    catalog["database"] = _resolve(service_root, database_value)
    raw["catalog"] = catalog

    datasets = []
    for item in raw.get("datasets") or []:
        normalized = dict(item)
        for key in ("benchmark_path", "corpus_path"):
            if normalized.get(key):
                normalized[key] = _resolve(service_root, normalized[key])
        datasets.append(normalized)
    raw["datasets"] = datasets

    config = DashboardConfig(
        service_root=service_root,
        config_path=selected,
        **raw,
    )
    config.output_root.mkdir(parents=True, exist_ok=True)
    config.catalog.database.parent.mkdir(parents=True, exist_ok=True)
    return config
