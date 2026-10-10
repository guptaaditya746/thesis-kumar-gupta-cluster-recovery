import argparse
import json
import os
import sys
from pathlib import Path

BOOTSTRAP_ROOT = Path(__file__).resolve().parents[2]
VENV_PYTHON = BOOTSTRAP_ROOT / ".venv/bin/python"

if (
    VENV_PYTHON.exists()
    and Path(sys.executable).resolve() != VENV_PYTHON.resolve()
    and os.environ.get("M4_ANSWERING_REEXEC") != "1"
):
    env = dict(os.environ)
    env["M4_ANSWERING_REEXEC"] = "1"
    os.execve(str(VENV_PYTHON), [str(VENV_PYTHON), __file__, *sys.argv[1:]], env)

if __package__ in (None, ""):
    sys.path.insert(0, str(BOOTSTRAP_ROOT))

for site_packages in sorted((BOOTSTRAP_ROOT / ".venv" / "lib").glob("python*/site-packages")):
    sys.path.insert(0, str(site_packages))

from backend.app.answering.answering_service import (  # noqa: E402
    AnsweringService,
    DEFAULT_ANSWER_PATH,
    DEFAULT_RDF_PATH,
    DEFAULT_SPARQL_PATH,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
GRAPH_PATCH_DIR = PROJECT_ROOT / "backend/app/data/graph_patches"

DEMO_QUESTIONS = {
    "autograph": "Which paper proposes a reinforcement-learning approach for knowledge graph construction?",
    "lightrag": "Which paper argues that graph structures improve retrieval by capturing relationships between entities?",
    "mind_the_query": "Which paper discusses validation of generated graph queries?",
}

DEMO_PATCH_FILENAMES = {
    "autograph": "sample_graph_patch_autograph.json",
    "lightrag": "sample_graph_patch_lightrag.json",
    "mind_the_query": "sample_graph_patch_mind_the_query.json",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the Milestone 4 RDF-to-SPARQL answering pipeline."
    )
    parser.add_argument(
        "--demo",
        choices=sorted(DEMO_QUESTIONS),
        default="autograph",
        help="Named milestone 4 demo question to run.",
    )
    parser.add_argument(
        "--all-demos",
        action="store_true",
        help="Run all named milestone 4 demos.",
    )
    parser.add_argument(
        "--question",
        help="Override the selected demo question.",
    )
    parser.add_argument(
        "--patch",
        help="Optional explicit graph patch JSON path.",
    )
    return parser.parse_args()


def infer_patch_path(demo: str, patch: str | None) -> Path:
    if patch:
        return Path(patch).expanduser().resolve()
    return GRAPH_PATCH_DIR / DEMO_PATCH_FILENAMES[demo]


def load_graph_patch(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(f"Missing graph patch file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def trace_details(response: dict, step: str) -> dict:
    matches = [entry["details"] for entry in response["trace"] if entry["step"] == step]
    if not matches:
        return {}
    details = matches[-1]
    return details if isinstance(details, dict) else {}


def print_summary(question: str, patch: dict, response: dict) -> None:
    rdf_details = trace_details(response, "rdf_materialized")
    validation_details = trace_details(response, "sparql_validated")
    query_result = response["query_result"]

    print("Question:")
    print(question)
    print()
    print("Graph patch:")
    print(f"Nodes: {len(patch['nodes'])}")
    print(f"Edges: {len(patch['edges'])}")
    print()
    print("RDF:")
    print(f"Triples: {rdf_details.get('triple_count', 0)}")
    print(f"Saved: {rdf_details.get('serialization', DEFAULT_RDF_PATH.relative_to(PROJECT_ROOT))}")
    print()
    print("SPARQL validation:")
    print("PASSED" if validation_details.get("valid") else "FAILED")
    if validation_details.get("errors"):
        for error in validation_details["errors"]:
            print(f"- {error}")
    print()
    print("Execution:")
    if query_result["status"] == "success":
        print(f"Rows: {query_result['row_count']}")
    else:
        print(f"Status: {query_result['status']}")
        if query_result.get("error"):
            print(query_result["error"])
    print()
    print("Answer:")
    print(response["answer"])
    print()
    print("Saved:")
    print(DEFAULT_ANSWER_PATH.relative_to(PROJECT_ROOT))
    print(DEFAULT_SPARQL_PATH.relative_to(PROJECT_ROOT))


def run_demo(demo: str, *, question: str, patch_path: Path) -> dict:
    patch = load_graph_patch(patch_path)
    service = AnsweringService()
    response = service.answer_from_graph_patch(question=question, graph_patch=patch)
    return {"patch": patch, "response": response}


def main() -> None:
    args = parse_args()

    if args.all_demos:
        if args.question:
            raise SystemExit("--question cannot be combined with --all-demos.")
        if args.patch:
            raise SystemExit("--patch cannot be combined with --all-demos.")

        failures: list[str] = []
        for demo, demo_question in DEMO_QUESTIONS.items():
            print(f"=== Demo: {demo} ===")
            result = run_demo(
                demo,
                question=demo_question,
                patch_path=infer_patch_path(demo, None),
            )
            print_summary(demo_question, result["patch"], result["response"])
            if result["response"]["query_result"]["status"] != "success":
                failures.append(demo)
            elif result["response"]["query_result"]["row_count"] == 0:
                failures.append(demo)
            print()

        if failures:
            raise SystemExit(f"Demo failures: {', '.join(failures)}")
        return

    demo = args.demo
    question = args.question or DEMO_QUESTIONS[demo]
    patch_path = infer_patch_path(demo, args.patch)
    result = run_demo(demo, question=question, patch_path=patch_path)
    print_summary(question, result["patch"], result["response"])

    if result["response"]["query_result"]["status"] != "success":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
