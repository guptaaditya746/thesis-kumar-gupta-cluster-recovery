from __future__ import annotations

from pathlib import Path

from query_driven.corpus import FileCorpusAdapter, JsonlCorpusAdapter


def test_jsonl_corpus_loads_one_record_from_a_validated_byte_offset(tmp_path: Path):
    first = b'{"id":"doc-1","contents":"first document"}\n'
    second = b'{"id":"doc-2","contents":"selected evidence"}\n'
    corpus_file = tmp_path / "wiki_dump.jsonl"
    corpus_file.write_bytes(first + second)

    corpus = JsonlCorpusAdapter(
        root=tmp_path,
        corpus_file="wiki_dump.jsonl",
        id_field="id",
        content_field="contents",
    )

    document = corpus.resolve(
        {
            "kind": "jsonl_record",
            "path": "wiki_dump.jsonl",
            "byte_offset": len(first),
            "document_id": "doc-2",
        }
    )

    assert document.id == "doc-2"
    assert document.text == "selected evidence"
    assert document.reference.to_jsonable() == {
        "kind": "jsonl_record",
        "path": "wiki_dump.jsonl",
        "byte_offset": len(first),
        "document_id": "doc-2",
    }


def test_file_corpus_loads_a_relative_document_without_exposing_outside_paths(tmp_path: Path):
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "biology-42.txt").write_text("selected BRIGHT evidence", encoding="utf-8")
    corpus = FileCorpusAdapter(root=tmp_path)

    document = corpus.resolve({"kind": "file", "path": "nested/biology-42.txt"})

    assert document.id == "biology-42"
    assert document.text == "selected BRIGHT evidence"
    assert document.reference.to_jsonable() == {
        "kind": "file",
        "path": "nested/biology-42.txt",
        "document_id": "biology-42",
    }
