import json
from pathlib import Path

import backend.scripts.run_milestone_3_extraction as runner

from backend.app.extraction.schemas import GraphPatch, KGEdge, KGNode, NodeType, EdgeType, Provenance
from backend.app.retrieval.schemas import RetrievedChunk
from backend.scripts.run_milestone_3_extraction import (
    DemoRunResult,
    PipelineStageError,
    infer_output_path,
    print_failure,
    run_all_demos,
    run_demo,
    run_pipeline,
)


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
                    id="paper_1",
                    type=NodeType.PAPER,
                    label="AutoGraph-R1",
                    provenance=provenance,
                ),
                KGNode(
                    id="method_1",
                    type=NodeType.METHOD,
                    label="AutoGraph-R1",
                    provenance=provenance,
                ),
                KGNode(
                    id="task_1",
                    type=NodeType.TASK,
                    label="knowledge graph construction",
                    provenance=provenance,
                ),
            ],
            edges=[
                KGEdge(
                    source="paper_1",
                    target="method_1",
                    type=EdgeType.PROPOSES,
                    provenance=provenance,
                ),
                KGEdge(
                    source="method_1",
                    target="task_1",
                    type=EdgeType.ADDRESSES_TASK,
                    provenance=provenance,
                ),
            ],
        ).model_dump()


class EmptyRetrievalService:
    def retrieve(self, question: str, top_k: int = 5) -> list[RetrievedChunk]:
        return []


def test_run_pipeline_returns_cleaned_patch_and_reports():
    payload = run_pipeline(
        "What method does AutoGraph-R1 propose for knowledge graph construction?",
        retrieval_service=StubRetrievalService(),
        extractor=StubExtractor(),
    )

    assert payload["top_paper_id"] == "autograph_r1"
    assert payload["query_intent"].intent_type == "method_proposal"
    assert payload["raw_validation"].is_valid is True
    assert payload["resolved_validation"].is_valid is True
    assert payload["cleanup_result"].validation_report.is_valid is True
    assert len(payload["cleaned_patch"].nodes) == 3
    assert len(payload["cleaned_patch"].edges) == 2


def test_run_pipeline_raises_stage_error_for_empty_retrieval():
    try:
        run_pipeline(
            "What is AutoGraph-R1?",
            retrieval_service=EmptyRetrievalService(),
            extractor=StubExtractor(),
        )
    except PipelineStageError as exc:
        assert exc.stage == "retrieval"
        assert "No chunks were retrieved" in str(exc)
    else:
        raise AssertionError("Expected PipelineStageError for empty retrieval.")


def test_infer_output_path_uses_expected_demo_filename():
    path = infer_output_path("autograph", None)
    assert path.name == "sample_graph_patch_autograph.json"
    assert isinstance(path, Path)



def _stub_payload():
    return run_pipeline(
        "What method does AutoGraph-R1 propose for knowledge graph construction?",
        retrieval_service=StubRetrievalService(),
        extractor=StubExtractor(),
    )


def test_run_demo_saves_cleaned_patch(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "count_contextualized_chunks", lambda: 7)
    monkeypatch.setattr(runner, "run_pipeline", lambda question, top_k=5: _stub_payload())

    output_path = tmp_path / "sample_graph_patch_autograph.json"
    result = run_demo(
        "autograph",
        question="What method does AutoGraph-R1 propose for knowledge graph construction?",
        output_path=output_path,
        top_k=5,
    )

    assert result.error is None
    assert result.contextualized_chunk_count == 7
    assert output_path.exists()
    saved = json.loads(output_path.read_text())
    assert len(saved["nodes"]) == 3
    assert len(saved["edges"]) == 2


def test_run_all_demos_writes_expected_artifacts(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "count_contextualized_chunks", lambda: 3)
    monkeypatch.setattr(runner, "run_pipeline", lambda question, top_k=5: _stub_payload())
    monkeypatch.setattr(runner, "infer_output_path", lambda demo, output: tmp_path / f"{demo}.json")

    results = run_all_demos(top_k=4)

    assert len(results) == len(runner.DEMO_QUESTIONS)
    assert {result.demo for result in results} == set(runner.DEMO_QUESTIONS)
    assert all(result.error is None for result in results)
    assert all(result.output_path.exists() for result in results)


def test_print_failure_includes_demo_and_stage(capsys):
    result = DemoRunResult(
        demo="autograph",
        question="What is AutoGraph-R1?",
        output_path=Path("/tmp/sample_graph_patch_autograph.json"),
        contextualized_chunk_count=12,
        error=PipelineStageError("retrieval", "boom"),
    )

    print_failure(result)
    captured = capsys.readouterr()
    assert "Demo: autograph" in captured.err
    assert "Contextualized chunks loaded: 12" in captured.err
    assert "retrieval failed: boom" in captured.err
