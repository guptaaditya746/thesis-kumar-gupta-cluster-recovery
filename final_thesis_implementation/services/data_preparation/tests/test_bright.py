from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("pyarrow")
import pyarrow as pa
import pyarrow.parquet as pq
from thesis_data_prep.bright import export_documents, safe_relative_path


def test_safe_relative_path_rejects_traversal() -> None:
    with pytest.raises(ValueError):
        safe_relative_path("../escape.txt")


def test_export_bright_preserves_document_path(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    pq.write_table(
        pa.table({"id": ["topic/doc.txt"], "content": ["searchable content"]}),
        source / "part.parquet",
    )
    output = tmp_path / "docs"

    count = export_documents(source, output)

    assert count == 1
    assert (output / "topic" / "doc.txt").read_text(encoding="utf-8") == "searchable content"
    marker = json.loads((output / ".data_prep_complete.json").read_text(encoding="utf-8"))
    assert marker["records"] == 1
