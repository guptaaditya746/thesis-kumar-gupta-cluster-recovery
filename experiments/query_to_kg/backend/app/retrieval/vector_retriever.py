import json
from pathlib import Path

from backend.app.retrieval.schemas import ContextualChunk, RetrievedChunk
from llama_index.core import VectorStoreIndex, StorageContext, load_index_from_storage
from backend.app.llm_config import build_embedding_model

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CHUNKS_PATH = PROJECT_ROOT / "backend/app/data/chunks/contextualized_chunks.jsonl"
VECTOR_INDEX_DIR = PROJECT_ROOT / "backend/app/data/indexes/llamaindex_vector"

def load_chunks_by_id(path: Path) -> dict[str, ContextualChunk]:
    chunks_by_id = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            data = json.loads(line)
            chunk = ContextualChunk(**data)
            chunks_by_id[chunk.chunk_id] = chunk
    return chunks_by_id

def load_vector_index(persist_dir: Path) -> VectorStoreIndex:
    if not persist_dir.exists():
        raise FileNotFoundError(
            f"Vector index directory not found: {persist_dir}. "
            "Run index_builder.py first."
        )

    embed_model = build_embedding_model()

    storage_context = StorageContext.from_defaults(persist_dir=str(persist_dir))
    index = load_index_from_storage(
        storage_context,
        embed_model=embed_model
    )
    return index

def retrieve_vector(question: str, top_k: int = 5) -> list[RetrievedChunk]:
    chunks_by_id = load_chunks_by_id(CHUNKS_PATH)
    index = load_vector_index(VECTOR_INDEX_DIR)

    retriever = index.as_retriever(similarity_top_k=top_k)
    node_results = retriever.retrieve(question)

    retrieved_chunks = []
    for rank, node_with_score in enumerate(node_results, start=1):
        chunk_id = (
            node_with_score.node.metadata.get("chunk_id")
            or node_with_score.node.node_id
        )

        if chunk_id not in chunks_by_id:
            print(f"Warning: Chunk ID {chunk_id} found in index but not in source JSONL.")
            continue

        original_chunk = chunks_by_id[chunk_id]

        retrieved_chunk = RetrievedChunk(
            chunk_id=original_chunk.chunk_id,
            paper_id=original_chunk.paper_id,
            paper_title=original_chunk.paper_title,
            section_id=original_chunk.section_id,
            section_title=original_chunk.section_title,
            raw_text=original_chunk.raw_text,
            contextual_summary=original_chunk.contextual_summary or "",
            score=float(node_with_score.score or 0.0),
            retrieval_method="vector",
            rank=rank,
            page_start=original_chunk.page_start,
            page_end=original_chunk.page_end,
        )
        retrieved_chunks.append(retrieved_chunk)

    return retrieved_chunks

def main() -> None:
    question = "What is LightRAG?"
    print(f"Querying: '{question}'\n")

    try:
        results = retrieve_vector(question, top_k=5)

        if not results:
            print("No results found.")
            return

        for result in results:
            print(f"Rank {result.rank} | score={result.score:.4f}")
            print(f"chunk_id={result.chunk_id}")
            print(f"paper_title={result.paper_title}")
            print(f"section_title={result.section_title}")
            print(f"raw_text preview={result.raw_text[:150]}...\n")

    except Exception as e:
        print(f"Retrieval failed: {e}")

if __name__ == "__main__":
    main()
