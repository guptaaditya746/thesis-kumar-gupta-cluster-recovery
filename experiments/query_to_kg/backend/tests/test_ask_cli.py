import argparse
import json
from pathlib import Path
from types import SimpleNamespace

import backend.scripts.ask as ask
from backend.app.extraction.schemas import EdgeType, GraphPatch, KGEdge, KGNode, NodeType, Provenance
from backend.app.retrieval.schemas import RetrievedChunk
from backend.scripts.run_milestone_3_extraction import run_pipeline


class StubRetrievalService:
    def retrieve(self, question: str, top_k: int = 5) -> list[RetrievedChunk]:
        return [
            RetrievedChunk(
                chunk_id="chunk_001",
                paper_id="autograph_r1",
                paper_title="AutoGraph-R1",
                section_id="section_001",
                section_title="Introduction",
                raw_text="AutoGraph-R1 proposes a reinforcement learning approach for knowledge graph construction.",
                contextual_summary="AutoGraph-R1 proposes an RL method for KG construction.",
                score=0.91,
                retrieval_method="hybrid_rrf",
                rank=1,
            )
        ]


class StubExtractor:
    def extract_graph_patch(self, question: str, intent, retrieved_chunks):
        provenance = Provenance(
            paper_id="autograph_r1",
            chunk_id="chunk_001",
            text_span="AutoGraph-R1 proposes a reinforcement learning approach for knowledge graph construction.",
        )
        return GraphPatch(
            nodes=[
                KGNode(
                    id="paper:autograph_r1",
                    type=NodeType.PAPER,
                    label="AutoGraph-R1",
                    properties={"title": "AutoGraph-R1"},
                    provenance=provenance,
                ),
                KGNode(
                    id="method:autograph_r1",
                    type=NodeType.METHOD,
                    label="AutoGraph-R1",
                    properties={"name": "AutoGraph-R1"},
                    provenance=provenance,
                ),
                KGNode(
                    id="task:knowledge_graph_construction",
                    type=NodeType.TASK,
                    label="knowledge graph construction",
                    properties={"name": "knowledge graph construction"},
                    provenance=provenance,
                ),
            ],
            edges=[
                KGEdge(
                    source="paper:autograph_r1",
                    target="method:autograph_r1",
                    type=EdgeType.PROPOSES,
                    provenance=provenance,
                ),
                KGEdge(
                    source="method:autograph_r1",
                    target="task:knowledge_graph_construction",
                    type=EdgeType.ADDRESSES_TASK,
                    provenance=provenance,
                ),
            ],
        ).model_dump()


def _payload() -> dict:
    return run_pipeline(
        "What method does AutoGraph-R1 propose for knowledge graph construction?",
        retrieval_service=StubRetrievalService(),
        extractor=StubExtractor(),
    )


def test_write_response_creates_json_file(tmp_path):
    path = tmp_path / "answer.json"

    ask.write_response(path, {"answer": "test"})

    assert json.loads(path.read_text(encoding="utf-8")) == {"answer": "test"}


def test_print_answer_summary_includes_core_sections(tmp_path, capsys):
    payload = _payload()
    response = {
        "answer": "AutoGraph-R1 proposes a reinforcement learning method.",
        "query": "SELECT ?paper WHERE { ?paper ?p ?o } LIMIT 5",
        "query_result": {
            "status": "success",
            "row_count": 1,
            "columns": ["paper"],
            "rows": [{"paper": "AutoGraph-R1"}],
            "error": None,
        },
        "evidence": [
            {
                "paper_id": "autograph_r1",
                "section_title": "Introduction",
                "chunk_id": "chunk_001",
                "text_span": "AutoGraph-R1 proposes a reinforcement learning approach for knowledge graph construction.",
            }
        ],
        "trace": [{"step": "sparql_executed", "details": {"row_count": 1}}],
    }

    ask.print_answer_summary(
        question="What method does AutoGraph-R1 propose for knowledge graph construction?",
        payload=payload,
        response=response,
        graph_path=tmp_path / "graph.json",
        response_path=tmp_path / "answer.json",
        contextualized_count=7,
        show_graph=True,
        show_sparql=True,
        show_trace=True,
    )

    captured = capsys.readouterr()
    assert "Question: What method does AutoGraph-R1 propose" in captured.out
    assert "Retrieved chunks:" in captured.out
    assert "Graph patch:" in captured.out
    assert "SPARQL:" in captured.out
    assert "Trace:" in captured.out
    assert "AutoGraph-R1 proposes a reinforcement learning method." in captured.out


def test_read_question_rejects_empty_interactive_input(monkeypatch):
    class Args:
        question = None

    monkeypatch.setattr("builtins.input", lambda prompt: "")

    try:
        ask.read_question(Args())
    except SystemExit as exc:
        assert "question is required" in str(exc).lower()
    else:
        raise AssertionError("Expected SystemExit for empty question.")


def test_positive_int_rejects_non_positive_values():
    try:
        ask.positive_int("0")
    except argparse.ArgumentTypeError as exc:
        assert "at least 1" in str(exc)
    else:
        raise AssertionError("Expected --top-k validation to reject zero.")


def test_read_question_rejects_blank_positional_question():
    args = SimpleNamespace(question="   ")

    try:
        ask.read_question(args)
    except SystemExit as exc:
        assert "non-empty question" in str(exc).lower()
    else:
        raise AssertionError("Expected SystemExit for blank positional question.")


def test_run_once_returns_false_and_prints_failure(monkeypatch, tmp_path, capsys):
    args = SimpleNamespace(
        top_k=5,
        graph_output=str(tmp_path / "graph.json"),
        response_output=str(tmp_path / "answer.json"),
        json=False,
        show_graph=False,
        show_sparql=False,
        show_trace=False,
    )

    def fail_answer_question(*args, **kwargs):
        return ask.AskRunResult(
            payload=None,
            response=None,
            contextualized_count=3,
            error=ask.PipelineStageError("retrieval", "No chunks were retrieved."),
        )

    monkeypatch.setattr(ask, "answer_question", fail_answer_question)

    assert ask.run_once(args, "What fails?") is False
    captured = capsys.readouterr()
    assert "Question: What fails?" in captured.err
    assert "Contextualized chunks loaded: 3" in captured.err
    assert "retrieval failed: No chunks were retrieved." in captured.err

def test_batch_testing_writes_20_question_results(monkeypatch, tmp_path):
    args = SimpleNamespace(
        top_k=5,
        graph_output=str(tmp_path / "graph.json"),
        response_output=str(tmp_path / "answer.json"),
        batch_output=str(tmp_path / "batch.json"),
    )

    def fake_answer_question(question, *, top_k, graph_output, response_output):
        return ask.AskRunResult(
            payload={},
            response={
                "answer": f"generated: {question}",
                "query": "SELECT ?s WHERE { ?s ?p ?o } LIMIT 1",
                "query_result": {"status": "success", "row_count": 1},
                "evidence": [],
                "trace": [],
            },
            contextualized_count=7,
        )

    monkeypatch.setattr(ask, "answer_question", fake_answer_question)

    assert ask.run_batch_testing(args) is True

    payload = json.loads((tmp_path / "batch.json").read_text(encoding="utf-8"))
    assert payload["metadata"]["question_count"] == 20
    assert len(payload["results"]) == 20
    assert payload["results"][0]["golden_answer"]
    assert payload["results"][0]["generated_answer"].startswith("generated:")
    assert payload["results"][0]["status"] == "success"

