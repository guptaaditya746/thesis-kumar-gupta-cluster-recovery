import json
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, Field

from backend.app.retrieval.schemas import RetrievedChunk

PROJECT_ROOT = Path(__file__).resolve().parents[3]
RETRIEVAL_GOLD_PATH = PROJECT_ROOT / "backend/app/data/eval/retrieval_gold.json"


class RetrievalGoldExample(BaseModel):
    question: str
    expected_paper_id: str
    expected_terms: list[str] = Field(default_factory=list)


class RetrievalEvaluationReport(BaseModel):
    question: str
    expected_paper_id: str
    expected_terms: list[str] = Field(default_factory=list)
    results: list[RetrievedChunk]
    hit_at_1: bool
    hit_at_3: bool
    hit_at_5: bool
    expected_term_coverage: bool


class RetrievalMetrics(BaseModel):
    total_questions: int
    hit_at_1: int
    hit_at_3: int
    hit_at_5: int
    expected_term_coverage: int


class RetrievalClient(Protocol):
    def retrieve(self, question: str, top_k: int = 5) -> list[RetrievedChunk]:
        ...


def load_retrieval_gold(path: Path = RETRIEVAL_GOLD_PATH) -> list[RetrievalGoldExample]:
    with path.open("r", encoding="utf-8") as file:
        payload = json.load(file)

    return [RetrievalGoldExample.model_validate(item) for item in payload]


def has_expected_paper(
    results: list[RetrievedChunk],
    *,
    expected_paper_id: str,
    top_k: int,
) -> bool:
    return any(result.paper_id == expected_paper_id for result in results[:top_k])


def has_expected_terms_in_raw_text(
    results: list[RetrievedChunk],
    *,
    expected_terms: list[str],
    top_k: int = 5,
) -> bool:
    if not expected_terms:
        return True

    evidence_text = "\n".join(result.raw_text for result in results[:top_k]).lower()
    return all(term.lower() in evidence_text for term in expected_terms)


def evaluate_retrieval_example(
    example: RetrievalGoldExample,
    *,
    service: RetrievalClient,
    top_k: int = 5,
) -> RetrievalEvaluationReport:
    results = service.retrieve(example.question, top_k=top_k)

    return RetrievalEvaluationReport(
        question=example.question,
        expected_paper_id=example.expected_paper_id,
        expected_terms=example.expected_terms,
        results=results,
        hit_at_1=has_expected_paper(
            results,
            expected_paper_id=example.expected_paper_id,
            top_k=1,
        ),
        hit_at_3=has_expected_paper(
            results,
            expected_paper_id=example.expected_paper_id,
            top_k=3,
        ),
        hit_at_5=has_expected_paper(
            results,
            expected_paper_id=example.expected_paper_id,
            top_k=5,
        ),
        expected_term_coverage=has_expected_terms_in_raw_text(
            results,
            expected_terms=example.expected_terms,
            top_k=top_k,
        ),
    )


def evaluate_retrieval_examples(
    examples: list[RetrievalGoldExample],
    *,
    service: RetrievalClient,
    top_k: int = 5,
) -> list[RetrievalEvaluationReport]:
    return [
        evaluate_retrieval_example(example, service=service, top_k=top_k)
        for example in examples
    ]


def summarize_reports(
    reports: list[RetrievalEvaluationReport],
) -> RetrievalMetrics:
    return RetrievalMetrics(
        total_questions=len(reports),
        hit_at_1=sum(report.hit_at_1 for report in reports),
        hit_at_3=sum(report.hit_at_3 for report in reports),
        hit_at_5=sum(report.hit_at_5 for report in reports),
        expected_term_coverage=sum(report.expected_term_coverage for report in reports),
    )

