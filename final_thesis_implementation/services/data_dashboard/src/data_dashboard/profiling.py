from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from data_dashboard.readers import preview_file

ID_CANDIDATES = ("query_id", "docid", "document_id", "id", "qid", "topic_id")
QUESTION_CANDIDATES = ("query", "question", "topic", "title")
ANSWER_CANDIDATES = ("answer", "answers", "gold_answer", "response")
CONTENT_CANDIDATES = ("text", "contents", "content", "segment", "body", "document")


def profile_frame(frame: pd.DataFrame) -> dict[str, Any]:
    rows = len(frame)
    columns = list(frame.columns)
    missing = {
        str(column): int(frame[column].isna().sum())
        for column in columns
    }
    duplicate_rows = int(frame.astype(str).duplicated().sum()) if rows else 0

    id_column = next((name for name in ID_CANDIDATES if name in frame.columns), None)
    duplicate_ids = None
    if id_column:
        duplicate_ids = int(frame[id_column].astype(str).duplicated().sum())

    text_lengths: dict[str, dict[str, float | int]] = {}
    for column in columns:
        if frame[column].dtype == "object":
            lengths = frame[column].dropna().astype(str).str.len()
            if not lengths.empty:
                text_lengths[str(column)] = {
                    "min": int(lengths.min()),
                    "mean": float(lengths.mean()),
                    "median": float(lengths.median()),
                    "max": int(lengths.max()),
                }

    return {
        "sample_rows": rows,
        "columns": columns,
        "column_count": len(columns),
        "missing_values": missing,
        "duplicate_rows": duplicate_rows,
        "id_column": id_column,
        "duplicate_ids": duplicate_ids,
        "text_lengths": text_lengths,
    }


def profile_file(path: Path, sample_rows: int) -> tuple[pd.DataFrame, dict[str, Any]]:
    frame = preview_file(path, limit=sample_rows)
    frame = frame.replace({np.nan: None})
    return frame, profile_frame(frame)


def infer_semantic_columns(frame: pd.DataFrame) -> dict[str, str | None]:
    def first(candidates: tuple[str, ...]) -> str | None:
        return next((name for name in candidates if name in frame.columns), None)

    return {
        "id": first(ID_CANDIDATES),
        "question": first(QUESTION_CANDIDATES),
        "answer": first(ANSWER_CANDIDATES),
        "content": first(CONTENT_CANDIDATES),
    }
