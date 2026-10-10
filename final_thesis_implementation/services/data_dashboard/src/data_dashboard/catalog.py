from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

import duckdb

from data_dashboard.models import DashboardConfig
from data_dashboard.readers import record_count
from data_dashboard.utils import format_name, iter_files, stable_id


@dataclass(frozen=True)
class DatasetSource:
    dataset_id: str
    dataset_name: str
    artifact_type: str
    root_path: Path
    description: str | None = None


def connect(config: DashboardConfig, read_only: bool = False) -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(config.catalog.database), read_only=read_only)


def initialize_schema(connection: duckdb.DuckDBPyConnection) -> None:
    connection.execute("""
        CREATE TABLE IF NOT EXISTS catalog_runs (
            run_id VARCHAR PRIMARY KEY,
            started_at DOUBLE,
            completed_at DOUBLE,
            config_path VARCHAR,
            processed_root VARCHAR,
            status VARCHAR,
            details JSON
        )
    """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS datasets (
            dataset_key VARCHAR PRIMARY KEY,
            dataset_id VARCHAR,
            dataset_name VARCHAR,
            artifact_type VARCHAR,
            root_path VARCHAR,
            description VARCHAR,
            file_count BIGINT,
            scanned_file_count BIGINT,
            total_size_bytes BIGINT,
            record_count BIGINT,
            exact_record_count BOOLEAN,
            scan_truncated BOOLEAN,
            latest_mtime DOUBLE,
            cataloged_at DOUBLE,
            error VARCHAR
        )
    """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS files (
            file_id VARCHAR PRIMARY KEY,
            dataset_key VARCHAR,
            dataset_id VARCHAR,
            artifact_type VARCHAR,
            absolute_path VARCHAR,
            relative_path VARCHAR,
            file_name VARCHAR,
            format VARCHAR,
            size_bytes BIGINT,
            modified_at DOUBLE,
            record_count BIGINT,
            record_count_exact BOOLEAN,
            error VARCHAR
        )
    """)
    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_files_dataset ON files(dataset_key)
    """)


def discover_sources(config: DashboardConfig) -> list[DatasetSource]:
    if config.datasets:
        sources: list[DatasetSource] = []
        for dataset in config.datasets:
            if dataset.benchmark_path:
                sources.append(
                    DatasetSource(
                        dataset.id,
                        dataset.name,
                        "benchmark",
                        dataset.benchmark_path,
                        dataset.description,
                    )
                )
            if dataset.corpus_path:
                sources.append(
                    DatasetSource(
                        dataset.id, dataset.name, "corpus", dataset.corpus_path, dataset.description
                    )
                )
        return sources

    sources = []
    for artifact_type, folder in (
        ("benchmark", config.processed_root / "benchmarks"),
        ("corpus", config.processed_root / "corpora"),
    ):
        if not folder.exists():
            continue
        for child in sorted(folder.iterdir()):
            if child.is_dir() or child.is_symlink():
                sources.append(
                    DatasetSource(
                        dataset_id=child.name,
                        dataset_name=child.name.replace("_", " ").replace("-", " ").title(),
                        artifact_type=artifact_type,
                        root_path=child.resolve(strict=False),
                    )
                )
            elif child.is_file():
                sources.append(
                    DatasetSource(
                        dataset_id=child.stem,
                        dataset_name=child.stem.replace("_", " ").title(),
                        artifact_type=artifact_type,
                        root_path=child.resolve(strict=False),
                    )
                )
    return sources


def build_catalog(
    config: DashboardConfig,
    *,
    new_sources_only: bool = False,
    scan_limit: int | None = None,
) -> dict[str, int]:
    started = time.time()
    run_id = stable_id(str(started), str(config.config_path))
    connection = connect(config)
    initialize_schema(connection)
    connection.execute(
        "INSERT OR REPLACE INTO catalog_runs VALUES (?, ?, NULL, ?, ?, ?, ?)",
        [run_id, started, str(config.config_path), str(config.processed_root), "running", "{}"],
    )

    sources = discover_sources(config)
    totals = {"datasets": 0, "files": 0, "errors": 0}
    current_keys: set[str] = set()
    existing_keys = {
        row[0] for row in connection.execute("SELECT dataset_key FROM datasets").fetchall()
    }
    maximum_files = min(
        config.catalog.max_files_per_dataset,
        scan_limit or config.catalog.max_files_per_dataset,
    )

    try:
        for source in sources:
            dataset_key = f"{source.artifact_type}:{source.dataset_id}"
            current_keys.add(dataset_key)
            if new_sources_only and dataset_key in existing_keys:
                continue
            connection.execute("DELETE FROM files WHERE dataset_key = ?", [dataset_key])

            root = source.root_path
            if not root.exists():
                connection.execute(
                    """INSERT OR REPLACE INTO datasets VALUES
                       (?, ?, ?, ?, ?, ?, 0, 0, 0, NULL, false, false, NULL, ?, ?)""",
                    [
                        dataset_key,
                        source.dataset_id,
                        source.dataset_name,
                        source.artifact_type,
                        str(root),
                        source.description,
                        time.time(),
                        "Path does not exist",
                    ],
                )
                totals["errors"] += 1
                continue

            files = (
                [root]
                if root.is_file()
                else iter_files(root, follow_symlinks=config.catalog.follow_symlinks)
            )
            file_count = 0
            scanned = 0
            size_total = 0
            count_total = 0
            exact_all = True
            latest_mtime = 0.0
            truncated = False
            dataset_error: str | None = None
            file_batch: list[list[object]] = []

            try:
                for path in files:
                    file_count += 1
                    if scanned >= maximum_files:
                        truncated = True
                        break
                    scanned += 1
                    stat = path.stat()
                    size_total += stat.st_size
                    latest_mtime = max(latest_mtime, stat.st_mtime)
                    count, exact = record_count(path, config.catalog.exact_count_max_bytes)
                    if count is not None:
                        count_total += count
                    else:
                        exact_all = False
                    if not exact:
                        exact_all = False
                    relative = path.name if root.is_file() else str(path.relative_to(root))
                    file_id = stable_id(dataset_key, str(path))
                    file_batch.append(
                        [
                            file_id,
                            dataset_key,
                            source.dataset_id,
                            source.artifact_type,
                            str(path.resolve(strict=False)),
                            relative,
                            path.name,
                            format_name(path),
                            stat.st_size,
                            stat.st_mtime,
                            count,
                            exact,
                        ]
                    )
                    if len(file_batch) >= 2_000:
                        connection.executemany(
                            """INSERT OR REPLACE INTO files VALUES
                               (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)""",
                            file_batch,
                        )
                        file_batch.clear()
                if file_batch:
                    connection.executemany(
                        """INSERT OR REPLACE INTO files VALUES
                           (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)""",
                        file_batch,
                    )
            except Exception as exc:
                dataset_error = f"{type(exc).__name__}: {exc}"
                totals["errors"] += 1

            connection.execute(
                """INSERT OR REPLACE INTO datasets VALUES
                   (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    dataset_key,
                    source.dataset_id,
                    source.dataset_name,
                    source.artifact_type,
                    str(root),
                    source.description,
                    file_count,
                    scanned,
                    size_total,
                    count_total if exact_all else None,
                    exact_all,
                    truncated,
                    latest_mtime or None,
                    time.time(),
                    dataset_error,
                ],
            )
            totals["datasets"] += 1
            totals["files"] += scanned

        existing = connection.execute("SELECT dataset_key FROM datasets").fetchall()
        for (dataset_key,) in existing:
            if dataset_key not in current_keys:
                connection.execute("DELETE FROM files WHERE dataset_key = ?", [dataset_key])
                connection.execute("DELETE FROM datasets WHERE dataset_key = ?", [dataset_key])

        completed = time.time()
        connection.execute(
            "UPDATE catalog_runs SET completed_at = ?, status = ?, details = ? WHERE run_id = ?",
            [completed, "complete", json.dumps(totals), run_id],
        )
        connection.commit()
        return totals
    except Exception as exc:
        connection.execute(
            "UPDATE catalog_runs SET completed_at = ?, status = ?, details = ? WHERE run_id = ?",
            [time.time(), "failed", json.dumps({"error": str(exc)}), run_id],
        )
        connection.commit()
        raise
    finally:
        connection.close()


def catalog_exists(config: DashboardConfig) -> bool:
    if not config.catalog.database.exists():
        return False
    try:
        connection = connect(config, read_only=True)
        connection.execute("SELECT 1 FROM datasets LIMIT 1").fetchall()
        connection.close()
        return True
    except Exception:
        return False
