from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from query_driven.config import load_config
from query_driven.corpus import FileCorpusAdapter, JsonlCorpusAdapter
from query_driven.evaluation import evaluate_answer_qa, evaluate_retrieval, run_evaluation
from query_driven.retrieval import (
    parse_retrieval_output,
    retrieval_prompt,
    run_retrieval_stage,
)


def test_retrieval_parser_validates_paths_and_normalizes_document_ids(tmp_path: Path):
    (tmp_path / "abc.txt").write_text("evidence", encoding="utf-8")
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested" / "def.txt").write_text("evidence", encoding="utf-8")
    raw = """<retrieval_result>
{"documents": [
  {"path": "abc.txt", "rank": 1},
  {"path": "nested/def.txt", "rank": 2},
  {"path": "../secret.txt", "rank": 3}
]}
</retrieval_result>"""
    result = parse_retrieval_output(
        raw,
        query_id="q1",
        question="question",
        corpus_root=tmp_path,
        top_k=20,
    )
    assert [item.document_id for item in result.documents] == ["abc", "def"]
    assert [item.path.as_posix() for item in result.documents] == ["abc.txt", "nested/def.txt"]


def test_retrieval_parser_returns_a_loaded_jsonl_record(tmp_path: Path):
    first = b'{"id":"0","contents":"unrelated"}\n'
    (tmp_path / "wiki_dump.jsonl").write_bytes(
        first + b'{"id":"42","contents":"the selected evidence"}\n'
    )
    corpus = JsonlCorpusAdapter(
        root=tmp_path,
        corpus_file="wiki_dump.jsonl",
        id_field="id",
        content_field="contents",
    )
    raw = f"""<retrieval_result>
{{"documents":[{{
  "kind":"jsonl_record",
  "path":"wiki_dump.jsonl",
  "byte_offset":{len(first)},
  "document_id":"42",
  "rank":1
}}]}}
</retrieval_result>"""

    result = parse_retrieval_output(
        raw,
        query_id="q1",
        question="question",
        corpus=corpus,
        top_k=20,
    )

    assert result.documents[0].document_id == "42"
    assert result.documents[0].text == "the selected evidence"


def test_retrieval_prompt_does_not_accept_gold_fields(tmp_path: Path):
    prompt = retrieval_prompt(
        question="Which university did X attend?",
        pattern="Person -> educated_at -> University",
        corpus_root=tmp_path,
        top_k=20,
    )
    assert "Which university did X attend?" in prompt
    for secret in ("gold_ids", "supporting_facts", "doc1", "gold answer"):
        assert secret not in prompt


def test_qa_evaluator_dispatch_metrics():
    result = evaluate_answer_qa(
        {"q1": "The University of Paris"},
        [{"id": "q1", "answer": ["University of Paris", "Paris University"]}],
        gold_field="answer",
        prediction_field="answer",
        metrics=["exact_match", "token_f1"],
    )
    assert result["per_item"]["q1"]["exact_match"] == 1.0
    assert result["per_item"]["q1"]["token_f1"] == 1.0
    assert result["overall"]["exact_match"] == 100.0


def test_document_id_is_filename_stem(tmp_path: Path):
    (tmp_path / "abc.txt").write_text("x", encoding="utf-8")
    raw = "<retrieval_result>{\"documents\":[{\"path\":\"" + str(tmp_path / "abc.txt") + "\",\"rank\":1}]}</retrieval_result>"
    result = parse_retrieval_output(
        raw,
        query_id="q1",
        question="q",
        corpus_root=tmp_path,
        top_k=1,
    )
    assert [item.document_id for item in result.documents] == ["abc"]

def test_retrieval_resume_skips_pi(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "abc.txt").write_text("evidence", encoding="utf-8")
    output = tmp_path / "output"
    query_dir = output / "retrieval" / "q1"
    query_dir.mkdir(parents=True)
    corpus_adapter = FileCorpusAdapter(root=corpus)
    (query_dir / "retrieval.json").write_text(
        json.dumps({
            "query_id": "q1",
            "question": "question",
            "corpus_fingerprint": corpus_adapter.fingerprint(),
            "documents": [{
                "kind": "file",
                "document_id": "abc",
                "path": "abc.txt",
                "rank": 1,
            }],
        }),
        encoding="utf-8",
    )
    (query_dir / "retrieval_raw.txt").write_text("cached", encoding="utf-8")

    cfg = load_config(Path(__file__).parents[1] / "config" / "qa" / "nq.toml")
    cfg.runtime.output_root = output
    cfg.runtime.concurrency = 1
    cfg.dataset.corpus_format = "files"
    cfg.dataset.corpus_root = corpus

    async def fail_pi(*args, **kwargs):
        raise AssertionError("Pi must not be invoked when retrieval.json is valid")

    monkeypatch.setattr("query_driven.retrieval._run_pi", fail_pi)
    result = asyncio.run(run_retrieval_stage(
        cfg,
        [{"query_id": "q1", "query": "question"}],
        corpus,
    ))
    assert result["q1"].documents[0].document_id == "abc"


def test_unfinalized_agent_output_is_not_promoted_to_a_retrieval_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "inspected.txt").write_text("candidate evidence", encoding="utf-8")
    cfg = load_config(Path(__file__).parents[1] / "config" / "qa" / "nq.toml")
    cfg.dataset.corpus_format = "files"
    cfg.dataset.corpus_root = corpus
    cfg.runtime.output_root = tmp_path / "output"
    cfg.runtime.resume = False
    cfg.runtime.concurrency = 1
    cfg.retrieval.use_query_pattern = False

    async def unfinished_pi(*args, **kwargs):
        return "I inspected inspected.txt but did not finalize."

    monkeypatch.setattr("query_driven.retrieval._run_pi", unfinished_pi)
    result = asyncio.run(
        run_retrieval_stage(
            cfg,
            [{"query_id": "q1", "query": "question"}],
            corpus,
        )
    )

    assert result["q1"].documents == []


def test_retrieval_evaluator_scores_ranked_ids():
    result = evaluate_retrieval(
        {"q1": ["wrong", "gold"]},
        [{"id": "q1", "gold_ids": ["gold"]}],
        metrics=["ndcg@10", "recall@10", "mrr"],
    )
    assert result["per_item"]["q1"]["recall@10"] == 1.0
    assert result["per_item"]["q1"]["mrr"] == 0.5


def test_pipeline_evaluation_scores_only_the_selected_question_ids(tmp_path: Path):
    predictions = tmp_path / "predictions.json"
    predictions.write_text('{"q1":"Paris"}', encoding="utf-8")
    gold = tmp_path / "gold.jsonl"
    gold.write_text(
        '{"query_id":"q1","answer":"Paris"}\n'
        '{"query_id":"q2","answer":"Berlin"}\n',
        encoding="utf-8",
    )

    result = run_evaluation(
        predictions_path=predictions,
        gold_path=gold,
        output_path=tmp_path / "evaluation.json",
        kind="answer_qa",
        gold_field="answer",
        prediction_field="answer",
        selected_qids=["q1"],
    )

    assert result["overall"]["count"] == 1
    assert list(result["per_item"]) == ["q1"]
