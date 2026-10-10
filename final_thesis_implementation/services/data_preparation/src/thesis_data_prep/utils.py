from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from collections.abc import Iterable, Iterator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DATA_LAYOUT = (
    "raw/benchmarks",
    "raw/corpora",
    "interim",
    "processed/benchmarks",
    "processed/corpora",
    "manifests/downloads",
    "manifests/datasets",
    "checksums",
    "logs",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_data_layout(data_root: Path) -> None:
    for relative in DATA_LAYOUT:
        (data_root / relative).mkdir(parents=True, exist_ok=True)


def atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False
    ) as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
        temp_path = Path(handle.name)
    temp_path.replace(path)


def atomic_copy(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=target.parent, prefix=f".{target.name}.", delete=False) as handle:
        temp_path = Path(handle.name)
    try:
        shutil.copy2(source, temp_path)
        temp_path.replace(target)
    finally:
        temp_path.unlink(missing_ok=True)


def remove_path(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink(missing_ok=True)
    elif path.exists():
        shutil.rmtree(path)


def directory_has_files(path: Path) -> bool:
    return path.is_dir() and any(child.is_file() for child in path.rglob("*"))


def iter_files(path: Path, *, exclude_hidden_metadata: bool = True) -> Iterator[Path]:
    if path.is_file():
        yield path
        return
    if not path.exists():
        return
    for item in path.rglob("*"):
        if not item.is_file():
            continue
        if exclude_hidden_metadata and any(part in {".cache", ".git"} for part in item.parts):
            continue
        yield item


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_tree_fingerprint(path: Path, *, max_files: int = 200_000) -> dict[str, Any]:
    digest = hashlib.sha256()
    files = 0
    bytes_total = 0
    truncated = False

    for item in iter_files(path):
        if files >= max_files:
            truncated = True
            break
        stat = item.stat()
        relative = item.relative_to(path) if path.is_dir() else Path(item.name)
        digest.update(str(relative).encode("utf-8", errors="replace"))
        digest.update(str(stat.st_size).encode("ascii"))
        files += 1
        bytes_total += stat.st_size

    return {
        "files_scanned": files,
        "bytes_scanned": bytes_total,
        "truncated": truncated,
        "path_size_fingerprint_sha256": digest.hexdigest(),
    }


def human_bytes(value: int) -> str:
    units = ["B", "KiB", "MiB", "GiB", "TiB", "PiB"]
    size = float(value)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PiB"


def unique_preserving_order(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def relative_symlink(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    relative_source = os.path.relpath(source.resolve(), target.parent.resolve())
    target.symlink_to(relative_source, target_is_directory=source.is_dir())
