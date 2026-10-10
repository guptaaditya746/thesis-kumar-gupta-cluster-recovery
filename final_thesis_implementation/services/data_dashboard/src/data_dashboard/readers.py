from __future__ import annotations

import gzip
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import duckdb
import orjson
import pandas as pd
import pyarrow.parquet as pq
import streamlit as st

from data_dashboard.utils import format_name


def _jsonl_records(path: Path, limit: int) -> Iterator[dict[str, Any]]:
    opener = gzip.open if path.name.lower().endswith(".gz") else open
    with opener(path, "rb") as handle:
        emitted = 0
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            try:
                value = orjson.loads(line)
            except orjson.JSONDecodeError:
                value = {"_raw": line.decode("utf-8", errors="replace"), "_parse_error": True}
            if isinstance(value, dict):
                yield value
            else:
                yield {"value": value}
            emitted += 1
            if emitted >= limit:
                break


def _preview_file(path: Path, limit: int = 100) -> pd.DataFrame:
    fmt = format_name(path)
    if fmt == "parquet":
        escaped = str(path).replace("'", "''")
        return duckdb.sql(f"SELECT * FROM read_parquet('{escaped}') LIMIT {int(limit)}").df()
    if fmt in {"jsonl", "jsonl.gz"}:
        return pd.json_normalize(list(_jsonl_records(path, limit)))
    if fmt in {"csv", "tsv"}:
        separator = "\t" if fmt == "tsv" else ","
        return pd.read_csv(path, sep=separator, nrows=limit, on_bad_lines="skip")
    if fmt in {"json", "json.gz"}:
        opener = gzip.open if fmt.endswith(".gz") else open
        with opener(path, "rb") as handle:
            value = orjson.loads(handle.read())
        if isinstance(value, list):
            return pd.json_normalize(value[:limit])
        if isinstance(value, dict):
            for key in ("data", "records", "items", "topics", "queries"):
                nested = value.get(key)
                if isinstance(nested, list):
                    return pd.json_normalize(nested[:limit])
            return pd.json_normalize([value])
    if fmt in {"txt", "md"}:
        text = path.read_text(encoding="utf-8", errors="replace")
        return pd.DataFrame([{"path": str(path), "text": text}])
    raise ValueError(f"Unsupported preview format: {fmt}")


def _revision(path: Path) -> tuple[int, int]:
    stat = path.stat()
    return (stat.st_mtime_ns, stat.st_size)


@st.cache_data(show_spinner=False, max_entries=64)
def _cached_preview(path_text: str, limit: int, revision: tuple[int, int]) -> pd.DataFrame:
    del revision
    return _preview_file(Path(path_text), limit)


def preview_file(path: Path, limit: int = 100) -> pd.DataFrame:
    """Read a bounded preview and reuse it until the source file changes."""
    safe_path = path.resolve(strict=False)
    return _cached_preview(str(safe_path), limit, _revision(safe_path))


def record_count(path: Path, exact_count_max_bytes: int) -> tuple[int | None, bool]:
    fmt = format_name(path)
    try:
        if fmt == "parquet":
            return int(pq.ParquetFile(path).metadata.num_rows), True
        if fmt in {"txt", "md"}:
            return 1, True
        if path.stat().st_size > exact_count_max_bytes:
            return None, False
        if fmt in {"jsonl", "jsonl.gz", "csv", "tsv"}:
            opener = gzip.open if fmt.endswith(".gz") else open
            with opener(path, "rb") as handle:
                count = sum(1 for line in handle if line.strip())
            if fmt in {"csv", "tsv"} and count:
                count -= 1
            return max(count, 0), True
        if fmt in {"json", "json.gz"}:
            frame = preview_file(path, limit=1_000_000)
            return len(frame), True
    except Exception:
        return None, False
    return None, False


def text_preview(path: Path, max_characters: int = 20000) -> str:
    fmt = format_name(path)
    if fmt not in {"txt", "md"}:
        frame = preview_file(path, limit=10)
        return frame.to_json(orient="records", indent=2, force_ascii=False)[:max_characters]
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        return handle.read(max_characters)
