import argparse
import json
import os
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

BOOTSTRAP_ROOT = Path(__file__).resolve().parents[2]
VENV_PYTHON = BOOTSTRAP_ROOT / ".venv/bin/python"

if (
    VENV_PYTHON.exists()
    and Path(sys.executable).resolve() != VENV_PYTHON.resolve()
    and os.environ.get("M3_EXTRACTION_REEXEC") != "1"
):
    env = dict(os.environ)
    env["M3_EXTRACTION_REEXEC"] = "1"
    os.execve(str(VENV_PYTHON), [str(VENV_PYTHON), __file__, *sys.argv[1:]], env)

if __package__ in (None, ""):
    sys.path.insert(0, str(BOOTSTRAP_ROOT))

for site_packages in sorted((BOOTSTRAP_ROOT / ".venv" / "lib").glob("python*/site-packages")):
    sys.path.insert(0, str(site_packages))

from backend.app.extraction.kg_extractor import KGExtractor
from backend.app.extraction.query_understanding import QueryIntent, analyze_query
from backend.app.graph import clean_graph_patch, resolve_graph_patch, validate_graph_patch
from backend.app.retrieval.retrieval_service import RetrievalService
from backend.app.retrieval.schemas import RetrievedChunk

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONTEXTUALIZED_CHUNKS_PATH = PROJECT_ROOT / "backend/app/data/chunks/contextualized_chunks.jsonl"
GRAPH_PATCH_OUTPUT_DIR = PROJECT_ROOT / "backend/app/data/graph_patches"

DEMO_QUESTIONS = {
    "autograph": "What method does AutoGraph-R1 propose for knowledge graph construction?",
    "lightrag": "What evidence does LightRAG provide that graph structures improve retrieval?",
    "mind_the_query": "What benchmark or validation setting is described in Mind the Query?",
}

DEMO_OUTPUT_FILENAMES = {
    "autograph": "sample_graph_patch_autograph.json",
    "lightrag": "sample_graph_patch_lightrag.json",
    "mind_the_query": "sample_graph_patch_mind_the_query.json",
}


class PipelineStageError(RuntimeError):
    def __init__(self, stage: str, message: str):
        super().__init__(f"{stage} failed: {message}")
        self.stage = stage


@dataclass(frozen=True)
class DemoRunResult:
    demo: str
    question: str
    output_path: Path
    contextualized_chunk_count: int
    payload: dict[str, Any] | None = None
    error: PipelineStageError | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the Milestone 3 retrieval-to-graph extraction pipeline."
    )
    parser.add_argument(
        "--demo",
        choices=sorted(DEMO_QUESTIONS),
        default="autograph",
        help="Named demo question to run.",
    )
    parser.add_argument(
        "--all-demos",
        action="store_true",
        help="Run all named milestone demo questions and save their standard sample artifacts.",
    )
    parser.add_argument(
        "--question",
        help="Override the demo question with a custom question.",
    )
    parser.add_argument(
        "--output",
        help="Optional explicit output path for the cleaned graph patch JSON.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Number of retrieved chunks to pass to extraction.",
    )
    return parser.parse_args()


def count_contextualized_chunks(path: Path = CONTEXTUALIZED_CHUNKS_PATH) -> int:
    if not path.exists():
        raise PipelineStageError(
            "contextualized chunk loading",
            f"Missing contextualized chunk file at '{path}'.",
        )

    with path.open("r", encoding="utf-8") as file:
        return sum(1 for line in file if line.strip())


def chunk_text_by_id(results: list[RetrievedChunk]) -> dict[str, str]:
    return {result.chunk_id: result.raw_text for result in results}


def infer_output_path(demo: str, output: str | None) -> Path:
    if output:
        return Path(output).expanduser().resolve()
    return GRAPH_PATCH_OUTPUT_DIR / DEMO_OUTPUT_FILENAMES[demo]


def paper_counts(results: list[RetrievedChunk]) -> Counter[str]:
    return Counter(result.paper_id for result in results)


def top_paper_id(results: list[RetrievedChunk]) -> str:
    if not results:
        return "n/a"
    counts = paper_counts(results)
    top_count = counts.most_common(1)[0][1]
    for result in results:
        if counts[result.paper_id] == top_count:
            return result.paper_id
    return results[0].paper_id


def serialize_results(results: list[RetrievedChunk]) -> list[dict[str, Any]]:
    return [result.model_dump() for result in results]


def run_pipeline(
    question: str,
    *,
    top_k: int = 5,
    retrieval_service: RetrievalService | None = None,
    extractor: KGExtractor | None = None,
) -> dict[str, Any]:
    retrieval_service = retrieval_service or RetrievalService()
    extractor = extractor or KGExtractor()

    try:
        retrieved_chunks = retrieval_service.retrieve(question, top_k=top_k)
    except Exception as exc:
        raise PipelineStageError("retrieval", str(exc)) from exc

    if not retrieved_chunks:
        raise PipelineStageError("retrieval", "No chunks were retrieved.")

    try:
        intent = analyze_query(question)
    except Exception as exc:
        raise PipelineStageError("query understanding", str(exc)) from exc

    try:
        raw_patch = extractor.extract_graph_patch(
            question=question,
            intent=intent,
            retrieved_chunks=retrieved_chunks,
        )
    except Exception as exc:
        raise PipelineStageError("extraction", str(exc)) from exc

    try:
        raw_validation = validate_graph_patch(
            raw_patch,
            chunk_text_by_id=chunk_text_by_id(retrieved_chunks),
        )
    except Exception as exc:
        raise PipelineStageError("validation", str(exc)) from exc

    try:
        resolved_patch = resolve_graph_patch(raw_patch)
    except Exception as exc:
        raise PipelineStageError("entity resolution", str(exc)) from exc

    try:
        resolved_validation = validate_graph_patch(
            resolved_patch,
            chunk_text_by_id=chunk_text_by_id(retrieved_chunks),
        )
    except Exception as exc:
        raise PipelineStageError("validation", str(exc)) from exc

    try:
        cleanup_result = clean_graph_patch(
            resolved_patch,
            chunk_text_by_id=chunk_text_by_id(retrieved_chunks),
        )
    except Exception as exc:
        raise PipelineStageError("cleaning", str(exc)) from exc

    cleaned_patch = cleanup_result.patch

    return {
        "question": question,
        "query_intent": intent,
        "retrieved_chunks": retrieved_chunks,
        "raw_patch": raw_patch,
        "raw_validation": raw_validation,
        "resolved_patch": resolved_patch,
        "resolved_validation": resolved_validation,
        "cleanup_result": cleanup_result,
        "cleaned_patch": cleaned_patch,
        "top_paper_id": top_paper_id(retrieved_chunks),
    }


def save_cleaned_patch(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cleaned_patch = payload["cleaned_patch"]
    with path.open("w", encoding="utf-8") as file:
        json.dump(cleaned_patch.model_dump(), file, indent=2)
        file.write("\n")


def print_summary(
    payload: dict[str, Any],
    *,
    output_path: Path,
    contextualized_chunk_count: int,
) -> None:
    intent: QueryIntent = payload["query_intent"]
    retrieved_chunks: list[RetrievedChunk] = payload["retrieved_chunks"]
    cleaned_patch = payload["cleaned_patch"]
    cleanup_result = payload["cleanup_result"]
    raw_validation = payload["raw_validation"]
    resolved_validation = payload["resolved_validation"]
    final_validation = cleanup_result.validation_report

    print(f"Question: {payload['question']}")
    print(f"Contextualized chunks loaded: {contextualized_chunk_count}")
    print(f"Retrieved chunk count: {len(retrieved_chunks)}")
    print(f"Top paper: {payload['top_paper_id']}")
    print(f"Query type: {intent.intent_type}")
    print(f"Target entities: {', '.join(intent.target_entities) if intent.target_entities else 'n/a'}")
    print(f"Raw validation: {'valid' if raw_validation.is_valid else 'invalid'}")
    print(f"Resolved validation: {'valid' if resolved_validation.is_valid else 'invalid'}")
    print(f"Node count: {len(cleaned_patch.nodes)}")
    print(f"Edge count: {len(cleaned_patch.edges)}")
    print(f"Validation: {'valid' if final_validation.is_valid else 'invalid'}")
    print(f"Validation errors: {len(final_validation.errors)}")
    print(f"Validation warnings: {len(final_validation.warnings)}")
    print(f"Cleanup warnings: {len(cleanup_result.warnings)}")
    print(f"Saved graph patch: {output_path}")

    if retrieved_chunks:
        print("Retrieved chunks:")
        for chunk in retrieved_chunks:
            print(
                f"  {chunk.rank}. {chunk.paper_id} / {chunk.section_title} / "
                f"{chunk.chunk_id} / score={chunk.score:.4f}"
            )

    if final_validation.errors:
        print("Validation error details:")
        for error in final_validation.errors:
            print(f"  - {error}")

    if cleanup_result.warnings:
        print("Cleanup warnings:")
        for warning in cleanup_result.warnings:
            print(f"  - {warning}")


def run_demo(
    demo: str,
    *,
    question: str,
    output_path: Path,
    top_k: int,
) -> DemoRunResult:
    contextualized_count = count_contextualized_chunks()
    try:
        payload = run_pipeline(question, top_k=top_k)
    except PipelineStageError as exc:
        return DemoRunResult(
            demo=demo,
            question=question,
            output_path=output_path,
            contextualized_chunk_count=contextualized_count,
            error=exc,
        )

    save_cleaned_patch(output_path, payload)
    return DemoRunResult(
        demo=demo,
        question=question,
        output_path=output_path,
        contextualized_chunk_count=contextualized_count,
        payload=payload,
    )


def print_failure(result: DemoRunResult) -> None:
    if result.error is None:
        return
    print(f"Demo: {result.demo}", file=sys.stderr)
    print(f"Question: {result.question}", file=sys.stderr)
    print(
        f"Contextualized chunks loaded: {result.contextualized_chunk_count}",
        file=sys.stderr,
    )
    print(str(result.error), file=sys.stderr)


def run_all_demos(top_k: int) -> list[DemoRunResult]:
    results: list[DemoRunResult] = []
    for demo, question in DEMO_QUESTIONS.items():
        results.append(
            run_demo(
                demo,
                question=question,
                output_path=infer_output_path(demo, None),
                top_k=top_k,
            )
        )
    return results


def main() -> None:
    args = parse_args()
    if args.all_demos:
        if args.question:
            raise SystemExit("--question cannot be combined with --all-demos.")
        if args.output:
            raise SystemExit("--output cannot be combined with --all-demos.")

        results = run_all_demos(args.top_k)
        failures = [result for result in results if result.error is not None]

        for result in results:
            print(f"=== Demo: {result.demo} ===")
            if result.payload is not None:
                print_summary(
                    result.payload,
                    output_path=result.output_path,
                    contextualized_chunk_count=result.contextualized_chunk_count,
                )
            else:
                print_failure(result)

        if failures:
            raise SystemExit(1)
        return

    question = args.question or DEMO_QUESTIONS[args.demo]
    output_path = infer_output_path(args.demo, args.output)
    result = run_demo(
        args.demo,
        question=question,
        output_path=output_path,
        top_k=args.top_k,
    )
    if result.error is not None:
        print_failure(result)
        raise SystemExit(1)

    assert result.payload is not None
    print_summary(
        result.payload,
        output_path=result.output_path,
        contextualized_chunk_count=result.contextualized_chunk_count,
    )


if __name__ == "__main__":
    main()
