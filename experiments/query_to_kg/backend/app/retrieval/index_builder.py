import json
from pathlib import Path

from backend.app.retrieval.schemas import ContextualChunk
from llama_index.core import VectorStoreIndex
from llama_index.core.schema import TextNode
from backend.app.llm_config import build_embedding_model

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CHUNKS_PATH = PROJECT_ROOT / "backend/app/data/chunks/contextualized_chunks.jsonl"
VECTOR_INDEX_DIR = PROJECT_ROOT / "backend/app/data/indexes/llamaindex_vector"

def load_contextual_chunks(path: Path) -> list[ContextualChunk]:
    chunks = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            data = json.loads(line)
            chunks.append(ContextualChunk(**data))
    return chunks

def validate_chunks(chunks: list[ContextualChunk]) -> None:
    if not chunks:
        raise ValueError("No contextual chunks loaded.")

    seen_ids: set[str] = set()

    for chunk in chunks:
        if chunk.chunk_id in seen_ids:
            raise ValueError(f"Duplicate chunk_id found: {chunk.chunk_id}")

        seen_ids.add(chunk.chunk_id)

        if not chunk.index_text.strip():
            raise ValueError(f"Empty index_text for chunk_id={chunk.chunk_id}")

        if not chunk.raw_text.strip():
            raise ValueError(f"Empty raw_text for chunk_id={chunk.chunk_id}")

def chunk_to_node(chunk: ContextualChunk) -> TextNode:
    return TextNode(
        text=chunk.index_text,
        id_=chunk.chunk_id,
        metadata={
            "chunk_id": chunk.chunk_id,
            "paper_id": chunk.paper_id,
            "paper_title": chunk.paper_title,
            "section_id": chunk.section_id,
            "section_title": chunk.section_title,
            "chunk_index": chunk.chunk_index,
            "page_start": chunk.page_start,
            "page_end": chunk.page_end,
        }
    )

def build_vector_index(chunks: list[ContextualChunk]) -> VectorStoreIndex:
    embed_model = build_embedding_model()

    nodes = [chunk_to_node(chunk) for chunk in chunks]
    index = VectorStoreIndex(nodes, embed_model=embed_model)
    return index

def persist_index(index: VectorStoreIndex, persist_dir: Path) -> None:
    # LlamaIndex requires the directory to exist or it creates it during persist
    persist_dir.mkdir(parents=True, exist_ok=True)
    index.storage_context.persist(persist_dir=str(persist_dir))

def main() -> None:
    if not CHUNKS_PATH.exists():
        print(f"Error: Could not find {CHUNKS_PATH}")
        return

    chunks = load_contextual_chunks(CHUNKS_PATH)
    validate_chunks(chunks)
    print(f"Loaded contextual chunks: {len(chunks)}")

    index = build_vector_index(chunks)
    print("Built vector index")

    persist_index(index, VECTOR_INDEX_DIR)
    print(f"Persisted vector index: {VECTOR_INDEX_DIR}")

if __name__ == "__main__":
    main()
