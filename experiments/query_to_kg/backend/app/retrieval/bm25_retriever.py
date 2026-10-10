import json
import pickle
import re
from pathlib import Path

from rank_bm25 import BM25Okapi

from backend.app.retrieval.schemas import ContextualChunk, RetrievedChunk

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CHUNKS_PATH = PROJECT_ROOT / "backend/app/data/chunks/contextualized_chunks.jsonl"
BM25_INDEX_PATH = PROJECT_ROOT / "backend/app/data/indexes/bm25_index.pkl"

TOKEN_PATTERN = re.compile(r"[A-Za-z0-9]+(?:[-_][A-Za-z0-9]+)*")

def tokenize(text: str) -> list[str]:
    return [match.group(0).lower() for match in TOKEN_PATTERN.finditer(text)]

def load_contextual_chunks(path: Path) -> list[ContextualChunk]:
    chunks: list[ContextualChunk] = []

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue

            data = json.loads(line)
            chunks.append(ContextualChunk(**data))

    return chunks


def load_chunks_by_id(path: Path) -> dict[str, ContextualChunk]:
    chunks = load_contextual_chunks(path)
    return {chunk.chunk_id: chunk for chunk in chunks}


def build_bm25_text(chunk: ContextualChunk) -> str:
    # Safely handle missing retrieval_tags if they aren't populated yet
    tags_list = getattr(chunk, "retrieval_tags", [])
    tags = " ".join(tags_list) if tags_list else ""

    return "\n".join(
        [
            chunk.paper_title,
            chunk.section_title,
            chunk.contextual_summary or "",
            tags,
            chunk.raw_text,
        ]
    )

def build_bm25_index(chunks: list[ContextualChunk]) -> dict:
    chunk_ids = [chunk.chunk_id for chunk in chunks]
    texts = [build_bm25_text(chunk) for chunk in chunks]
    tokenized_corpus = [tokenize(text) for text in texts]

    bm25 = BM25Okapi(tokenized_corpus)

    return {
        "bm25": bm25,
        "chunk_ids": chunk_ids,
        "tokenized_corpus": tokenized_corpus,
    }

def persist_bm25_index(index_data: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("wb") as f:
        pickle.dump(index_data, f)

def load_bm25_index(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(
            f"BM25 index not found: {path}. Run bm25_retriever.py first."
        )

    with path.open("rb") as f:
        return pickle.load(f)

def retrieve_bm25(question: str, top_k: int = 5) -> list[RetrievedChunk]:
    chunks_by_id = load_chunks_by_id(CHUNKS_PATH)
    index_data = load_bm25_index(BM25_INDEX_PATH)

    bm25 = index_data["bm25"]
    chunk_ids = index_data["chunk_ids"]

    query_tokens = tokenize(question)
    scores = bm25.get_scores(query_tokens)

    ranked_indices = sorted(
        range(len(scores)),
        key=lambda i: scores[i],
        reverse=True,
    )[:top_k]

    results: list[RetrievedChunk] = []

    for rank, idx in enumerate(ranked_indices, start=1):
        chunk_id = chunk_ids[idx]

        if chunk_id not in chunks_by_id:
            print(f"Warning: Chunk ID {chunk_id} found in BM25 index but not in source JSONL.")
            continue

        chunk = chunks_by_id[chunk_id]

        results.append(
            RetrievedChunk(
                chunk_id=chunk.chunk_id,
                paper_id=chunk.paper_id,
                paper_title=chunk.paper_title,
                section_id=chunk.section_id,
                section_title=chunk.section_title,
                raw_text=chunk.raw_text,
                contextual_summary=chunk.contextual_summary or "",
                score=float(scores[idx]),
                retrieval_method="bm25",
                rank=rank,
                page_start=chunk.page_start,
                page_end=chunk.page_end,
            )
        )

    return results


def main() -> None:
    chunks = load_contextual_chunks(CHUNKS_PATH)
    print(f"Loaded contextual chunks: {len(chunks)}")

    index_data = build_bm25_index(chunks)
    print("Built BM25 index")

    persist_bm25_index(index_data, BM25_INDEX_PATH)
    print(f"Persisted BM25 index: {BM25_INDEX_PATH}")

    query = "AutoGraph-R1"
    print(f"\nQuery: {query}")

    results = retrieve_bm25(query, top_k=5)

    for result in results:
        print(f"Rank {result.rank} | score={result.score:.4f}")
        print(f"chunk_id={result.chunk_id}")
        print(f"paper_title={result.paper_title}")
        print(f"section_title={result.section_title}")
        print(f"raw_text preview={result.raw_text[:150]}...\n")
