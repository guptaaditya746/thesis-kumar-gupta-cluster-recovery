import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.app.retrieval.evaluation import (
    load_retrieval_gold,
    evaluate_retrieval_examples,
    summarize_reports,
)
from backend.app.retrieval.retrieval_service import RetrievalService


def yes_no(value: bool) -> str:
    return "yes" if value else "no"


def main() -> None:
    examples = load_retrieval_gold()
    service = RetrievalService()

    try:
        reports = evaluate_retrieval_examples(examples, service=service, top_k=5)
    except Exception as exc:
        raise RuntimeError(
            "Retrieval evaluation failed. Ensure retrieval indexes exist and "
            "the local embedding endpoint is available for query embeddings."
        ) from exc

    metrics = summarize_reports(reports)

    for report in reports:
        print(f"Question: {report.question}")
        print(f"Expected paper: {report.expected_paper_id}")
        print("Retrieved top 5:")

        for result in report.results:
            print(
                f"  {result.rank}. {result.paper_id} / {result.section_title} / "
                f"{result.chunk_id} / score={result.score:.4f}"
            )

        print(f"Expected paper in top 3: {yes_no(report.hit_at_3)}")
        print(f"Expected terms found: {yes_no(report.expected_term_coverage)}")
        print()

    print("Metrics:")
    print(f"Hit@1: {metrics.hit_at_1}/{metrics.total_questions}")
    print(f"Hit@3: {metrics.hit_at_3}/{metrics.total_questions}")
    print(f"Hit@5: {metrics.hit_at_5}/{metrics.total_questions}")
    print(
        "Expected term coverage: "
        f"{metrics.expected_term_coverage}/{metrics.total_questions}"
    )
    print(
        "Target Hit@3 = 3/3: "
        f"{'PASSED' if metrics.hit_at_3 == metrics.total_questions else 'FAILED'}"
    )


if __name__ == "__main__":
    main()
