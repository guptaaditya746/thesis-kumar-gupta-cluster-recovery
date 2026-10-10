from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("pyarrow")
import pyarrow as pa
import pyarrow.parquet as pq

from thesis_data_prep.bcplus import export_documents, extract_qa


def test_extract_qa_without_decryption(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    pq.write_table(
        pa.table(
            {
                "query_id": ["q1", "q2"],
                "query": ["Question one?", "Question two?"],
                "answer": ["A1", "A2"],
            }
        ),
        source / "part.parquet",
    )
    output = tmp_path / "processed" / "qa.jsonl"

    count = extract_qa(source, output, decrypt=False)

    records = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    assert count == 2
    assert records[0] == {"query_id": "q1", "query": "Question one?", "answer": "A1"}


def test_export_browsecomp_documents_domain_first(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    pq.write_table(
        pa.table(
            {
                "docid": ["1"],
                "text": ["Title: Example Document\n\nBody"],
                "url": ["https://Example.COM/path/page"],
            }
        ),
        source / "corpus.parquet",
    )
    output = tmp_path / "docs"

    count = export_documents(source, output)

    assert count == 1
    assert (output / "example.com" / "Example Document.txt").read_text(encoding="utf-8").endswith(
        "Body"
    )
    marker = json.loads((output / ".data_prep_complete.json").read_text(encoding="utf-8"))
    assert marker["records"] == 1
