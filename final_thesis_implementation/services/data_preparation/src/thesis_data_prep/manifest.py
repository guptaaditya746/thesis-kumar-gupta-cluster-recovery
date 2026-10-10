from __future__ import annotations

import platform
import sys
from pathlib import Path
from typing import Any

from thesis_data_prep import __version__
from thesis_data_prep.settings import ResolvedConfig
from thesis_data_prep.utils import atomic_write_json, sha256_file, stable_tree_fingerprint, utc_now
from thesis_data_prep.validation import validate_resource


def _describe_path(path: Path, *, max_files: int = 200_000) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "path": str(path),
        "exists": path.exists() or path.is_symlink(),
        "is_symlink": path.is_symlink(),
    }
    if not payload["exists"]:
        return payload
    if path.is_symlink():
        payload["symlink_target"] = str(path.resolve())
    if path.is_file():
        payload.update({"type": "file", "bytes": path.stat().st_size, "sha256": sha256_file(path)})
    elif path.is_dir():
        payload.update({"type": "directory", **stable_tree_fingerprint(path, max_files=max_files)})
    return payload


def write_dataset_manifest(settings: ResolvedConfig, dataset_name: str) -> Path:
    canonical, dataset = settings.dataset(dataset_name)
    resources = [dataset.benchmark, dataset.corpus]
    resource_payload: dict[str, Any] = {}
    for resource_name in resources:
        resource = settings.resource(resource_name)
        validation = validate_resource(settings, resource_name)
        resource_payload[resource_name] = {
            "kind": resource.kind,
            "processor": resource.processor,
            "repository": resource.repository,
            "source": _describe_path(
                settings.resource_source(resource_name), max_files=1_000 if resource.large else 200_000
            ),
            "output": _describe_path(
                settings.resource_output(resource_name), max_files=1_000 if resource.large else 200_000
            ),
            "validation": {
                "ok": validation.ok,
                "details": validation.details,
                "errors": validation.errors,
            },
        }

    manifest_path = settings.data_root / "manifests" / "datasets" / f"{canonical}.json"
    atomic_write_json(
        manifest_path,
        {
            "schema_version": 1,
            "dataset": canonical,
            "description": dataset.description,
            "created_at": utc_now(),
            "service_version": __version__,
            "config_path": str(settings.config_path),
            "workspace_root": str(settings.workspace_root),
            "data_root": str(settings.data_root),
            "runtime": {
                "python": sys.version,
                "platform": platform.platform(),
                "hostname": platform.node(),
            },
            "resources": resource_payload,
        },
    )
    return manifest_path
