from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Iterable

SUPPORTED_SUFFIXES = {
    ".jsonl", ".json", ".parquet", ".csv", ".tsv", ".txt", ".md", ".gz"
}


def format_name(path: Path) -> str:
    lower = path.name.lower()
    if lower.endswith(".jsonl.gz"):
        return "jsonl.gz"
    if lower.endswith(".json.gz"):
        return "json.gz"
    return path.suffix.lower().lstrip(".") or "unknown"


def is_supported(path: Path) -> bool:
    lower = path.name.lower()
    return any(
        lower.endswith(suffix)
        for suffix in (
            ".jsonl", ".jsonl.gz", ".json", ".json.gz", ".parquet",
            ".csv", ".tsv", ".txt", ".md"
        )
    )


def safe_resolve(path: Path, allowed_roots: Iterable[Path]) -> Path:
    resolved = path.expanduser().resolve(strict=False)
    roots = [root.expanduser().resolve(strict=False) for root in allowed_roots]
    if not any(resolved == root or resolved.is_relative_to(root) for root in roots):
        raise ValueError(f"Path is outside configured read-only roots: {resolved}")
    return resolved


def stable_id(*parts: str) -> str:
    payload = "\x1f".join(parts).encode("utf-8", errors="replace")
    return hashlib.sha256(payload).hexdigest()[:24]


def iter_files(root: Path, follow_symlinks: bool = False):
    for dirpath, dirnames, filenames in os.walk(root, followlinks=follow_symlinks):
        if not follow_symlinks:
            dirnames[:] = [
                d for d in dirnames if not (Path(dirpath) / d).is_symlink()
            ]
        for filename in filenames:
            path = Path(dirpath) / filename
            if path.is_file() and is_supported(path):
                yield path
