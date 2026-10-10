from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import streamlit as st

from data_dashboard.utils import safe_resolve


def read_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def read_jsonl(path: Path, *, maximum_rows: int = 100_000) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if len(rows) >= maximum_rows:
                    break
                try:
                    value = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(value, dict):
                    rows.append(value)
    except OSError:
        return []
    return rows


def _discover_experiment_runs(root: Path) -> list[dict[str, Any]]:
    if not root.is_dir():
        return []
    runs: list[dict[str, Any]] = []
    for directory in root.iterdir():
        if not directory.is_dir():
            continue
        manifest = read_json_object(directory / "manifest.json")
        summary = read_json_object(directory / "summary.json")
        if not manifest and not summary:
            continue
        provenance = manifest.get("provenance") or {}
        agent = provenance.get("agent") or {}
        runs.append(
            {
                "run_id": str(manifest.get("run_id") or directory.name),
                "run_dir": str(directory.resolve()),
                "benchmark": manifest.get("benchmark") or summary.get("benchmark_name"),
                "task_type": manifest.get("task_type") or summary.get("task_type"),
                "status": manifest.get("status"),
                "created_at": manifest.get("created_at"),
                "model": agent.get("model"),
                "primary_metric_name": summary.get("primary_metric_name"),
                "primary_metric_value": summary.get("primary_metric_value"),
                "attempted_count": summary.get("attempted_count"),
                "completed_count": summary.get("completed_count"),
                "agent_timeouts": summary.get("agent_timeouts"),
                "tool_error_rate": summary.get("tool_error_rate"),
                "mean_latency_seconds": summary.get("mean_sample_latency_seconds"),
                "total_tokens": summary.get("total_tokens"),
            }
        )
    return sorted(runs, key=lambda row: str(row.get("created_at") or row["run_id"]), reverse=True)


def _load_run_results(run_dir: Path, root: Path) -> list[dict[str, Any]]:
    safe = safe_resolve(run_dir, [root])
    return read_jsonl(safe / "results.jsonl")


def _load_sample_artifacts(run_dir: Path, item_dir: str, root: Path) -> dict[str, Any]:
    safe_run = safe_resolve(run_dir, [root])
    safe_item = safe_resolve(safe_run / item_dir, [safe_run])
    return {
        "input": read_json_object(safe_item / "input.json"),
        "result": read_json_object(safe_item / "result.json"),
        "score": read_json_object(safe_item / "score.json"),
        "usage": read_json_object(safe_item / "usage.json"),
        "tools": read_json_object(safe_item / "tools.json"),
        "prompt": (safe_item / "prompt.txt").read_text(encoding="utf-8", errors="replace")
        if (safe_item / "prompt.txt").is_file()
        else "",
        "final": (safe_item / "final.txt").read_text(encoding="utf-8", errors="replace")
        if (safe_item / "final.txt").is_file()
        else "",
        "stderr": (safe_item / "stderr.txt").read_text(encoding="utf-8", errors="replace")
        if (safe_item / "stderr.txt").is_file()
        else "",
    }


def _revision(path: Path) -> tuple[int, int]:
    """Return a cheap cache key that changes whenever a file changes."""
    try:
        stat = path.stat()
    except OSError:
        return (0, 0)
    return (stat.st_mtime_ns, stat.st_size)


@st.cache_data(ttl=5, show_spinner=False)
def _cached_discovery(root_text: str) -> list[dict[str, Any]]:
    return _discover_experiment_runs(Path(root_text))


def discover_experiment_runs(root: Path) -> list[dict[str, Any]]:
    # A short TTL keeps active runs fresh while making page transitions immediate.
    return _cached_discovery(str(root.resolve(strict=False)))


@st.cache_data(show_spinner=False, max_entries=32)
def _cached_run_results(
    run_text: str, root_text: str, revision: tuple[int, int]
) -> list[dict[str, Any]]:
    del revision
    return _load_run_results(Path(run_text), Path(root_text))


def load_run_results(run_dir: Path, root: Path) -> list[dict[str, Any]]:
    safe = safe_resolve(run_dir, [root])
    return _cached_run_results(
        str(safe), str(root.resolve(strict=False)), _revision(safe / "results.jsonl")
    )


@st.cache_data(show_spinner=False, max_entries=128)
def _cached_sample_artifacts(
    run_text: str, item_dir: str, root_text: str, revisions: tuple[tuple[int, int], ...]
) -> dict[str, Any]:
    del revisions
    return _load_sample_artifacts(Path(run_text), item_dir, Path(root_text))


def load_sample_artifacts(run_dir: Path, item_dir: str, root: Path) -> dict[str, Any]:
    safe_run = safe_resolve(run_dir, [root])
    safe_item = safe_resolve(safe_run / item_dir, [safe_run])
    names = (
        "input.json",
        "result.json",
        "score.json",
        "usage.json",
        "tools.json",
        "prompt.txt",
        "final.txt",
        "stderr.txt",
    )
    revisions = tuple(_revision(safe_item / name) for name in names)
    return _cached_sample_artifacts(
        str(safe_run), item_dir, str(root.resolve(strict=False)), revisions
    )


__all__ = [
    "discover_experiment_runs",
    "load_run_results",
    "load_sample_artifacts",
    "read_json_object",
    "read_jsonl",
]
