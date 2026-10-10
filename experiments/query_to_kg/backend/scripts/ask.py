import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BOOTSTRAP_ROOT = Path(__file__).resolve().parents[2]
VENV_PYTHON = BOOTSTRAP_ROOT / ".venv/bin/python"

if (
    VENV_PYTHON.exists()
    and Path(sys.executable).resolve() != VENV_PYTHON.resolve()
    and os.environ.get("ASK_REEXEC") != "1"
):
    env = dict(os.environ)
    env["ASK_REEXEC"] = "1"
    os.execve(str(VENV_PYTHON), [str(VENV_PYTHON), __file__, *sys.argv[1:]], env)

if __package__ in (None, ""):
    sys.path.insert(0, str(BOOTSTRAP_ROOT))

for site_packages in sorted((BOOTSTRAP_ROOT / ".venv" / "lib").glob("python*/site-packages")):
    sys.path.insert(0, str(site_packages))

from backend.app.answering.answering_service import AnsweringService  # noqa: E402
from backend.scripts.run_milestone_3_extraction import (  # noqa: E402
    PipelineStageError,
    count_contextualized_chunks,
    run_pipeline,
    save_cleaned_patch,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_GRAPH_PATCH_PATH = PROJECT_ROOT / "backend/app/data/graph_patches/latest_ask_graph_patch.json"
DEFAULT_RESPONSE_PATH = PROJECT_ROOT / "backend/app/data/answers/latest_ask_response.json"
DEFAULT_BATCH_OUTPUT_PATH = PROJECT_ROOT / "backend/app/data/answers/batch_testing_answers.json"


BATCH_TEST_CASES = [
    {
        "id": "q01",
        "question": "Which paper proposes a reinforcement-learning approach for knowledge graph construction?",
        "golden_answer": "AutoGraph-R1 proposes a reinforcement-learning approach for knowledge graph construction.",
    },
    {
        "id": "q02",
        "question": "What does AutoGraph-R1 optimize KG construction for?",
        "golden_answer": "AutoGraph-R1 optimizes knowledge graph construction for downstream task performance.",
    },
    {
        "id": "q03",
        "question": "How does AutoGraph-R1 frame graph generation?",
        "golden_answer": "AutoGraph-R1 frames graph generation as a policy learning problem.",
    },
    {
        "id": "q04",
        "question": "Where does AutoGraph-R1 derive its reward signal from?",
        "golden_answer": "AutoGraph-R1 derives reward from the graph's functional utility in a RAG pipeline.",
    },
    {
        "id": "q05",
        "question": "What task does the AutoGraph-R1 method address?",
        "golden_answer": "The AutoGraph-R1 method addresses knowledge graph construction.",
    },
    {
        "id": "q06",
        "question": "Which paper argues that graph structures improve retrieval by capturing relationships between entities?",
        "golden_answer": "LightRAG argues that graph structures improve retrieval by capturing relationships or interdependencies between entities.",
    },
    {
        "id": "q07",
        "question": "What does LightRAG incorporate into text indexing and retrieval?",
        "golden_answer": "LightRAG incorporates graph structures into text indexing and retrieval processes.",
    },
    {
        "id": "q08",
        "question": "Why are graphs useful in LightRAG?",
        "golden_answer": "Graphs represent interdependencies among entities, enabling a more nuanced understanding of relationships.",
    },
    {
        "id": "q09",
        "question": "What does LightRAG combine with graph structures for retrieval?",
        "golden_answer": "LightRAG combines graph structures with vector representations for efficient retrieval of related entities and relationships.",
    },
    {
        "id": "q10",
        "question": "What kind of retrieval improvement does LightRAG claim from graph structures?",
        "golden_answer": "LightRAG claims graph structures improve contextual relevance and response time by retrieving related entities and relationships efficiently.",
    },
    {
        "id": "q11",
        "question": "Which paper discusses validation of generated graph queries?",
        "golden_answer": "Mind the Query discusses validation of generated graph queries.",
    },
    {
        "id": "q12",
        "question": "What task is Mind the Query built around?",
        "golden_answer": "Mind the Query is built around the Text2Cypher task: translating natural language questions into executable Cypher queries over graph databases.",
    },
    {
        "id": "q13",
        "question": "What does the Mind the Query dataset contain?",
        "golden_answer": "It contains 27,529 natural-language-to-Cypher query pairs across 11 real-world graph databases.",
    },
    {
        "id": "q14",
        "question": "What validation checks does Mind the Query use?",
        "golden_answer": "Mind the Query uses automated schema, runtime, and value checks followed by manual logical validation.",
    },
    {
        "id": "q15",
        "question": "What runtime issue does Mind the Query validation try to prevent?",
        "golden_answer": "It tries to prevent runtime mismatch errors during execution.",
    },
    {
        "id": "q16",
        "question": "Which paper presents a benchmark dataset for Text2Cypher?",
        "golden_answer": "Mind the Query presents a benchmark dataset for Text2Cypher.",
    },
    {
        "id": "q17",
        "question": "Which paper is about simple and fast retrieval-augmented generation?",
        "golden_answer": "LightRAG is about simple and fast retrieval-augmented generation.",
    },
    {
        "id": "q18",
        "question": "Which paper evaluates graph query generation with zero-shot, few-shot, and fine-tuned configurations?",
        "golden_answer": "Mind the Query evaluates graph query generation across zero-shot, few-shot, and fine-tuned configurations.",
    },
    {
        "id": "q19",
        "question": "Which paper introduces an end-to-end reinforcement learning framework for KG construction?",
        "golden_answer": "AutoGraph-R1 introduces an end-to-end reinforcement learning framework for knowledge graph construction.",
    },
    {
        "id": "q20",
        "question": "Which paper emphasizes relationships and interdependencies among entities for retrieval?",
        "golden_answer": "LightRAG emphasizes relationships and interdependencies among entities for retrieval.",
    },
]


@dataclass(frozen=True)
class AskRunResult:
    payload: dict[str, Any] | None
    response: dict[str, Any] | None
    contextualized_count: int
    error: PipelineStageError | None = None

    @property
    def succeeded(self) -> bool:
        return self.error is None


def positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc

    if parsed < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return parsed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ask a natural-language question through the query-to-KG pipeline."
    )
    parser.add_argument(
        "question",
        nargs="?",
        help="Natural-language question. If omitted, the script opens an interactive prompt.",
    )
    parser.add_argument(
        "--top-k",
        type=positive_int,
        default=5,
        help="Number of chunks to retrieve before graph extraction.",
    )
    parser.add_argument(
        "--graph-output",
        default=str(DEFAULT_GRAPH_PATCH_PATH),
        help="Path where the cleaned query-specific graph patch is saved.",
    )
    parser.add_argument(
        "--response-output",
        default=str(DEFAULT_RESPONSE_PATH),
        help="Path where the final answer response JSON is saved.",
    )
    parser.add_argument(
        "--batch-output",
        default=str(DEFAULT_BATCH_OUTPUT_PATH),
        help="Path where batch testing results are saved.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the full response object as JSON.",
    )
    parser.add_argument(
        "--show-graph",
        action="store_true",
        help="Print graph patch node and edge summaries.",
    )
    parser.add_argument(
        "--show-sparql",
        action="store_true",
        help="Print the generated SPARQL query.",
    )
    parser.add_argument(
        "--show-trace",
        action="store_true",
        help="Print trace step details.",
    )
    parser.add_argument(
        "--loop",
        action="store_true",
        help="Keep process alive and answer multiple questions.",
    )
    parser.add_argument(
        "--batch-testing",
        "--batch_testing",
        dest="batch_testing",
        action="store_true",
        help="Run the built-in 20-question batch test set and save golden/generated answers.",
    )
    return parser.parse_args()


def read_question(args: argparse.Namespace) -> str:
    if args.question is not None:
        question = args.question.strip()
        if question:
            return question
        raise SystemExit("A non-empty question is required.")

    try:
        question = input("Question: ").strip()
    except EOFError:
        question = ""

    if not question:
        raise SystemExit("A question is required.")
    return question


def write_response(path: Path, response: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(response, indent=2) + "\n", encoding="utf-8")
    return path


def build_batch_payload(*, top_k: int, results: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "metadata": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "question_count": len(BATCH_TEST_CASES),
            "top_k": top_k,
        },
        "results": results,
    }


def relative_display(path: Path) -> str:
    try:
        return path.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return str(path)


def print_retrieval_summary(payload: dict[str, Any]) -> None:
    print("\nRetrieved chunks:")
    retrieved_chunks = payload["retrieved_chunks"]
    if not retrieved_chunks:
        print("  n/a")
        return

    for chunk in retrieved_chunks:
        print(
            f"  {chunk.rank}. {chunk.paper_id} / {chunk.section_title} / "
            f"{chunk.chunk_id} / score={chunk.score:.4f}"
        )


def print_graph_summary(payload: dict[str, Any]) -> None:
    patch = payload["cleaned_patch"]
    print("\nGraph patch:")
    print(f"  Nodes: {len(patch.nodes)}")
    for node in patch.nodes:
        print(f"    - {node.id} ({node.type.value}): {node.label}")
    print(f"  Edges: {len(patch.edges)}")
    for edge in patch.edges:
        print(f"    - {edge.source} -[{edge.type.value}]-> {edge.target}")


def print_trace(response: dict[str, Any]) -> None:
    print("\nTrace:")
    for entry in response.get("trace", []):
        details = entry["details"]
        if isinstance(details, dict):
            compact = json.dumps(details, ensure_ascii=False)
        else:
            compact = str(details)
        print(f"  - {entry['step']}: {compact}")


def print_answer_summary(
    *,
    question: str,
    payload: dict[str, Any],
    response: dict[str, Any],
    graph_path: Path,
    response_path: Path,
    contextualized_count: int,
    show_graph: bool,
    show_sparql: bool,
    show_trace: bool,
) -> None:
    query_result = response["query_result"]
    cleanup_result = payload["cleanup_result"]

    print(f"Question: {question}")
    print(f"Contextualized chunks loaded: {contextualized_count}")
    print(f"Retrieved chunk count: {len(payload['retrieved_chunks'])}")
    print(f"Top paper: {payload['top_paper_id']}")
    print(f"Query type: {payload['query_intent'].intent_type}")
    print(f"Graph nodes: {len(payload['cleaned_patch'].nodes)}")
    print(f"Graph edges: {len(payload['cleaned_patch'].edges)}")
    print(f"Graph validation: {'valid' if cleanup_result.validation_report.is_valid else 'invalid'}")
    print(f"SPARQL status: {query_result['status']}")
    print(f"SPARQL rows: {query_result['row_count']}")

    print_retrieval_summary(payload)

    if show_graph:
        print_graph_summary(payload)

    if show_sparql:
        print("\nSPARQL:")
        print(response["query"])

    print("\nAnswer:")
    print(response["answer"])

    if response["evidence"]:
        print("\nEvidence:")
        for index, evidence in enumerate(response["evidence"], start=1):
            print(
                f"  {index}. {evidence['paper_id']} / {evidence.get('section_title')} / "
                f"{evidence['chunk_id']}"
            )
            print(f"     {evidence['text_span']}")

    if show_trace:
        print_trace(response)

    print("\nSaved:")
    print(f"  Graph patch: {relative_display(graph_path)}")
    print(f"  Answer response: {relative_display(response_path)}")


def answer_question(
    question: str,
    *,
    top_k: int,
    graph_output: Path,
    response_output: Path,
) -> AskRunResult:
    contextualized_count = 0

    try:
        contextualized_count = count_contextualized_chunks()
        payload = run_pipeline(question, top_k=top_k)
        save_cleaned_patch(graph_output, payload)
        response = AnsweringService().answer_from_graph_patch(
            question=question,
            graph_patch=payload["cleaned_patch"],
        )
        write_response(response_output, response)
    except PipelineStageError as exc:
        return AskRunResult(
            payload=None,
            response=None,
            contextualized_count=contextualized_count,
            error=exc,
        )
    except Exception as exc:
        return AskRunResult(
            payload=None,
            response=None,
            contextualized_count=contextualized_count,
            error=PipelineStageError("answering", str(exc)),
        )

    return AskRunResult(
        payload=payload,
        response=response,
        contextualized_count=contextualized_count,
    )


def print_failure(question: str, result: AskRunResult) -> None:
    if result.error is None:
        return

    print(f"Question: {question}", file=sys.stderr)
    print(
        f"Contextualized chunks loaded: {result.contextualized_count}",
        file=sys.stderr,
    )
    print(str(result.error), file=sys.stderr)


def run_once(args: argparse.Namespace, question: str) -> bool:
    graph_output = Path(args.graph_output).expanduser().resolve()
    response_output = Path(args.response_output).expanduser().resolve()

    result = answer_question(
        question,
        top_k=args.top_k,
        graph_output=graph_output,
        response_output=response_output,
    )
    if not result.succeeded:
        print_failure(question, result)
        return False

    assert result.payload is not None
    assert result.response is not None

    if args.json:
        print(json.dumps(result.response, indent=2))
        return True

    print_answer_summary(
        question=question,
        payload=result.payload,
        response=result.response,
        graph_path=graph_output,
        response_path=response_output,
        contextualized_count=result.contextualized_count,
        show_graph=args.show_graph,
        show_sparql=args.show_sparql,
        show_trace=args.show_trace,
    )
    return True


def run_batch_testing(args: argparse.Namespace) -> bool:
    batch_output = Path(args.batch_output).expanduser().resolve()
    graph_output = Path(args.graph_output).expanduser().resolve()
    response_output = Path(args.response_output).expanduser().resolve()
    results: list[dict[str, Any]] = []
    succeeded = True

    print(f"Running {len(BATCH_TEST_CASES)} batch questions...")
    for index, test_case in enumerate(BATCH_TEST_CASES, start=1):
        question = test_case["question"]
        print(f"[{index}/{len(BATCH_TEST_CASES)}] {question}")
        result = answer_question(
            question,
            top_k=args.top_k,
            graph_output=graph_output,
            response_output=response_output,
        )

        response = result.response or {}
        row = {
            "id": test_case["id"],
            "question": question,
            "golden_answer": test_case["golden_answer"],
            "generated_answer": response.get("answer"),
            "status": "success" if result.succeeded else "error",
            "error": str(result.error) if result.error else None,
            "contextualized_chunk_count": result.contextualized_count,
            "query": response.get("query"),
            "query_result": response.get("query_result"),
            "evidence": response.get("evidence", []),
            "trace": response.get("trace", []),
        }
        results.append(row)

        if not result.succeeded:
            succeeded = False

        write_response(batch_output, build_batch_payload(top_k=args.top_k, results=results))

    print(f"Saved batch results: {relative_display(batch_output)}")
    return succeeded


def main() -> None:
    args = parse_args()

    if args.batch_testing:
        if args.question:
            raise SystemExit("The positional question cannot be combined with --batch-testing.")
        if args.loop:
            raise SystemExit("--loop cannot be combined with --batch-testing.")
        if not run_batch_testing(args):
            raise SystemExit(1)
        return

    if args.loop:
        if args.question:
            raise SystemExit("The positional question cannot be combined with --loop.")

        print("Ask loop ready. Ctrl-C to exit.")
        while True:
            try:
                question = input("\nQuestion: ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                return

            if not question:
                continue

            run_once(args, question)
        return

    question = read_question(args)
    if not run_once(args, question):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
