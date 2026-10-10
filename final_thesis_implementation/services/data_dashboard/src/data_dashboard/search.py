from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pandas as pd


def ripgrep_search(
    root: Path,
    query: str,
    timeout_seconds: int,
    maximum_matches: int,
    maximum_matches_per_file: int,
) -> pd.DataFrame:
    if not query.strip():
        return pd.DataFrame(columns=["path", "line", "text"])
    if shutil.which("rg") is None:
        raise RuntimeError("ripgrep (rg) is not installed on this machine")

    command = [
        "rg", "--line-number", "--ignore-case", "--no-heading", "--color", "never",
        "--max-count", str(maximum_matches_per_file), "--max-columns", "300",
        "--glob", "*.txt", "--glob", "*.md", "--glob", "*.jsonl", "--glob", "*.json",
        query, str(root),
    ]
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        raise TimeoutError(f"Search exceeded {timeout_seconds} seconds") from exc

    if completed.returncode not in (0, 1):
        raise RuntimeError(completed.stderr.strip() or "ripgrep search failed")

    rows = []
    for line in completed.stdout.splitlines()[:maximum_matches]:
        parts = line.split(":", 2)
        if len(parts) == 3:
            path, line_number, text = parts
            rows.append({"path": path, "line": line_number, "text": text})
    return pd.DataFrame(rows)
