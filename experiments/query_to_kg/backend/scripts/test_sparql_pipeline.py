import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.answering.answering_service import AnsweringService  # noqa: E402
from backend.scripts.run_milestone_4_answering import (  # noqa: E402
    DEMO_PATCH_FILENAMES,
    DEMO_QUESTIONS,
    GRAPH_PATCH_DIR,
    load_graph_patch,
)

EXPECTED_ANSWER_TERMS = {
    "autograph": ["AutoGraph-R1", "reinforcement"],
    "lightrag": ["LightRAG", "relationship"],
    "mind_the_query": ["Mind the Query", "runtime"],
}


def main() -> None:
    service = AnsweringService()
    failures: list[str] = []

    for demo, question in DEMO_QUESTIONS.items():
        patch_path = GRAPH_PATCH_DIR / DEMO_PATCH_FILENAMES[demo]
        patch = load_graph_patch(patch_path)
        response = service.answer_from_graph_patch(question=question, graph_patch=patch)
        query_result = response["query_result"]
        answer = response["answer"]

        print(
            f"{demo}: status={query_result['status']} rows={query_result['row_count']} answer={answer}"
        )

        if query_result["status"] != "success":
            failures.append(f"{demo}: query status {query_result['status']}")
            continue
        if query_result["row_count"] == 0:
            failures.append(f"{demo}: empty result set")
            continue

        for term in EXPECTED_ANSWER_TERMS[demo]:
            if term.lower() not in answer.lower():
                failures.append(f"{demo}: answer missing '{term}'")

    if failures:
        for failure in failures:
            print(failure, file=sys.stderr)
        raise SystemExit(1)

    print("All Milestone 4 SPARQL demo runs succeeded.")


if __name__ == "__main__":
    main()
