from pathlib import Path

from query_driven.config import load_config


def test_example_config_loads():
    root = Path(__file__).resolve().parents[1]
    cfg = load_config(root / "config" / "examples" / "bright.toml")
    assert cfg.runtime.operation == "pipeline"
    assert cfg.text_model.model


def test_qa_smoke_config_declares_jsonl_record_storage():
    root = Path(__file__).resolve().parents[1]
    cfg = load_config(root / "config" / "smoke" / "qa-2wikimultihopqa.toml")

    assert cfg.dataset.corpus_format == "jsonl"
    assert cfg.dataset.corpus_file == "wiki_dump.jsonl"
    assert cfg.dataset.document_id_field == "id"
    assert cfg.dataset.document_content_field == "contents"
