from backend.app.retrieval.bm25_retriever import BM25_INDEX_PATH
from backend.app.retrieval.hybrid_retriever import retrieve_hybrid
from backend.app.retrieval.index_builder import VECTOR_INDEX_DIR
from backend.app.retrieval.schemas import RetrievedChunk


class RetrievalService:
    def __init__(self, vector_top_k: int = 20, bm25_top_k: int = 20) -> None:
        self.vector_top_k = vector_top_k
        self.bm25_top_k = bm25_top_k

    def _validate_indexes_exist(self) -> None:
        missing_paths: list[str] = []

        if not VECTOR_INDEX_DIR.exists():
            missing_paths.append(str(VECTOR_INDEX_DIR))

        if not BM25_INDEX_PATH.exists():
            missing_paths.append(str(BM25_INDEX_PATH))

        if missing_paths:
            missing_str = ", ".join(missing_paths)
            raise FileNotFoundError(
                "Retrieval indexes are missing. "
                "Run backend/scripts/build_retrieval_index.py first. "
                f"Missing: {missing_str}"
            )

    def retrieve(self, question: str, top_k: int = 5) -> list[RetrievedChunk]:
        if not question.strip():
            raise ValueError("Question must not be empty.")

        self._validate_indexes_exist()

        return retrieve_hybrid(
            question=question,
            top_k=top_k,
            vector_top_k=self.vector_top_k,
            bm25_top_k=self.bm25_top_k,
        )
