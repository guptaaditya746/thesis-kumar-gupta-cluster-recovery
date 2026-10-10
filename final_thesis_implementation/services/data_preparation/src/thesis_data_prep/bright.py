from __future__ import annotations

import json
import shutil
from pathlib import Path, PurePosixPath

import pyarrow.parquet as pq
from rich.console import Console
from tqdm import tqdm

from thesis_data_prep.utils import atomic_write_json, remove_path, utc_now

console = Console()
COMPLETE_MARKER = ".data_prep_complete.json"


def safe_relative_path(value: str) -> Path:
    relative = PurePosixPath(value)
    if relative.is_absolute() or not relative.parts or any(
        part in {"", ".", ".."} for part in relative.parts
    ):
        raise ValueError(f"Unsafe BRIGHT document id: {value!r}")
    return Path(*relative.parts)


def export_documents(source_dir: Path, output_dir: Path, *, force: bool = False) -> int:
    parquet_files = sorted(source_dir.glob("*.parquet"))
    if not parquet_files:
        raise FileNotFoundError(f"No parquet files found under {source_dir}")

    marker = output_dir / COMPLETE_MARKER
    if marker.exists() and not force:
        payload = json.loads(marker.read_text(encoding="utf-8"))
        console.print(f"[yellow]skip[/yellow] completed BRIGHT export: {output_dir}")
        return int(payload.get("records", 0))
    if output_dir.exists() and any(output_dir.iterdir()) and not force:
        raise RuntimeError(
            f"Output directory is non-empty but has no completion marker: {output_dir}. "
            "Use --force to rebuild it safely."
        )
    if force:
        remove_path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    total_docs = sum(pq.ParquetFile(path).metadata.num_rows for path in parquet_files)
    exported = 0
    progress = tqdm(total=total_docs, desc=f"Exporting BRIGHT {source_dir.name}", unit="doc")
    try:
        for parquet_file in parquet_files:
            parquet = pq.ParquetFile(parquet_file)
            required = {"id", "content"}
            missing = required.difference(parquet.schema_arrow.names)
            if missing:
                raise KeyError(f"{parquet_file} is missing columns: {sorted(missing)}")
            for batch in parquet.iter_batches(columns=["id", "content"], batch_size=4096):
                for row in batch.to_pylist():
                    target = output_dir / safe_relative_path(str(row["id"]))
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(str(row["content"] or ""), encoding="utf-8")
                    exported += 1
                    progress.update(1)
    except Exception:
        shutil.rmtree(output_dir, ignore_errors=True)
        raise
    finally:
        progress.close()

    atomic_write_json(
        marker,
        {
            "processor": "bright_docs",
            "records": exported,
            "source": str(source_dir.resolve()),
            "completed_at": utc_now(),
        },
    )
    console.print(f"[green]exported[/green] {exported:,} documents to {output_dir}")
    return exported
