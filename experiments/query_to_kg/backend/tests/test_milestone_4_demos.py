import pytest

import backend.app.answering.answering_service as answering_module
from backend.app.answering.answering_service import AnsweringService
from backend.tests.m4_fixtures import DEMO_CASES


@pytest.mark.parametrize(
    ("demo", "question", "patch_factory", "expected_terms"),
    DEMO_CASES,
)
def test_milestone_4_demo_questions_run_end_to_end(
    demo,
    question,
    patch_factory,
    expected_terms,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(answering_module, "DEFAULT_RDF_PATH", tmp_path / f"{demo}_graph.ttl")
    monkeypatch.setattr(answering_module, "DEFAULT_SPARQL_PATH", tmp_path / f"{demo}_query.rq")
    monkeypatch.setattr(answering_module, "DEFAULT_ANSWER_PATH", tmp_path / f"{demo}_answer.json")

    response = AnsweringService().answer_from_graph_patch(
        question=question,
        graph_patch=patch_factory(),
    )

    assert response["query_result"]["status"] == "success"
    assert response["query_result"]["row_count"] >= 1
    for term in expected_terms:
        assert term.lower() in response["answer"].lower()
