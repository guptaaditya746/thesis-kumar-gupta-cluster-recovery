import backend.app.answering.answering_service as answering_module
from backend.app.answering.answering_service import AnsweringService
from backend.tests.m4_fixtures import QUESTION, autograph_patch


def test_answering_service_returns_grounded_response_with_trace(tmp_path, monkeypatch):
    monkeypatch.setattr(answering_module, "DEFAULT_RDF_PATH", tmp_path / "latest_graph.ttl")
    monkeypatch.setattr(answering_module, "DEFAULT_SPARQL_PATH", tmp_path / "latest_query.rq")
    monkeypatch.setattr(answering_module, "DEFAULT_ANSWER_PATH", tmp_path / "latest_answer.json")

    response = AnsweringService().answer_from_graph_patch(
        question=QUESTION,
        graph_patch=autograph_patch(),
    )

    assert response["query_result"]["status"] == "success"
    assert response["query_result"]["row_count"] == 1
    assert response["evidence"][0]["chunk_id"] == "autograph_r1_abstract_0001"
    assert "AutoGraph-R1: End-to-End Reinforcement Learning for Knowledge Graph Construction" in response["answer"]
    assert "The evidence states that AutoGraph-R1 trains an LLM constructor" in response["answer"]
    assert response["query"].lstrip().startswith("PREFIX kg:")

    trace_steps = [entry["step"] for entry in response["trace"]]
    assert trace_steps == [
        "graph_patch_received",
        "rdf_materialized",
        "schema_context_built",
        "sparql_generated",
        "sparql_validated",
        "sparql_executed",
        "answer_generated",
    ]

    assert (tmp_path / "latest_graph.ttl").exists()
    assert (tmp_path / "latest_query.rq").exists()
    assert (tmp_path / "latest_answer.json").exists()
