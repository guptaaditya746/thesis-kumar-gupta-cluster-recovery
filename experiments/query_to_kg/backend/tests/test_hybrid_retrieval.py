import pytest

from backend.app.retrieval.evaluation import (
    evaluate_retrieval_examples,
    load_retrieval_gold,
    summarize_reports,
)
from backend.app.retrieval.retrieval_service import RetrievalService


def should_skip_runtime_dependency_error(exc: Exception) -> bool:
    message = str(exc)

    return any(
        marker in message
        for marker in [
            "Connection refused",
            "Retrieval indexes are missing",
            "http://127.0.0.1:8001/v1",
            "OpenAIException - Connection error",
            "InternalServerError",
        ]
    )


def test_hybrid_retrieval_hits_expected_papers_at_top_3() -> None:
    examples = load_retrieval_gold()
    service = RetrievalService()

    try:
        reports = evaluate_retrieval_examples(examples, service=service, top_k=5)
    except Exception as exc:
        if should_skip_runtime_dependency_error(exc):
            pytest.skip(f"Retrieval integration dependency unavailable: {exc}")
        raise

    metrics = summarize_reports(reports)

    assert len(reports) == 3
    assert metrics.hit_at_3 == metrics.total_questions
    assert metrics.hit_at_5 == metrics.total_questions
    assert metrics.expected_term_coverage == metrics.total_questions
