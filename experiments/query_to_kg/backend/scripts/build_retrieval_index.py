import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.app.llm_config import EMBED_API_BASE, EMBED_MODEL
from backend.app.retrieval.bm25_retriever import (
    BM25_INDEX_PATH,
    build_bm25_index,
    persist_bm25_index,
)
from backend.app.retrieval.index_builder import (
    CHUNKS_PATH,
    VECTOR_INDEX_DIR,
    build_vector_index,
    load_contextual_chunks,
    persist_index,
    validate_chunks,
)
from backend.app.retrieval.retrieval_service import RetrievalService
from backend.app.retrieval.schemas import RetrievedChunk

PROJECT_ROOT = Path(__file__).resolve().parents[2]
VALIDATION_QUERY = "What is LightRAG?"


def display_path(path: Path) -> str:
    try:
        return path.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return str(path)


def validate_retrieval_outputs() -> None:
    if not VECTOR_INDEX_DIR.exists():
        raise FileNotFoundError(f"Vector index directory not found: {VECTOR_INDEX_DIR}")

    if not BM25_INDEX_PATH.exists():
        raise FileNotFoundError(f"BM25 index file not found: {BM25_INDEX_PATH}")

    service = RetrievalService()

    try:
        results = service.retrieve(VALIDATION_QUERY, top_k=3)
    except Exception as exc:
        raise RuntimeError(
            "Retrieval validation failed. Ensure the local embedding service "
            f"is running at {EMBED_API_BASE} for query embeddings."
        ) from exc

    if not isinstance(results, list):
        raise ValueError("RetrievalService.retrieve did not return a list.")

    if not results:
        raise ValueError("RetrievalService.retrieve returned no results.")

    for result in results:
        payload = result.model_dump() if isinstance(result, RetrievedChunk) else result
        RetrievedChunk.model_validate(payload)


def main() -> None:
    if not CHUNKS_PATH.exists():
        raise FileNotFoundError(f"Contextualized chunks file not found: {CHUNKS_PATH}")

    chunks = load_contextual_chunks(CHUNKS_PATH)
    validate_chunks(chunks)
    print(f"Loaded contextual chunks: {len(chunks)}")

    try:
        vector_index = build_vector_index(chunks)
    except Exception as exc:
        raise RuntimeError(
            "Failed to build vector index. Ensure the local embedding service "
            f"is running at {EMBED_API_BASE} with model {EMBED_MODEL}."
        ) from exc

    persist_index(vector_index, VECTOR_INDEX_DIR)
    print(f"Built vector index: {display_path(VECTOR_INDEX_DIR)}")

    bm25_index = build_bm25_index(chunks)
    persist_bm25_index(bm25_index, BM25_INDEX_PATH)
    print(f"Built BM25 index: {display_path(BM25_INDEX_PATH)}")

    try:
        validate_retrieval_outputs()
    except Exception:
        print("Validation: FAILED")
        raise

    print("Validation: PASSED")


if __name__ == "__main__":
    main()
