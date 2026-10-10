from backend.app.retrieval.schemas import RetrievedChunk
from backend.app.retrieval.vector_retriever import retrieve_vector
from backend.app.retrieval.bm25_retriever import retrieve_bm25

def reciprocal_rank_fusion(
    vector_results: list[RetrievedChunk],
    bm25_results: list[RetrievedChunk],
    top_k: int = 5,
    rrf_k: int = 60,
) -> list[RetrievedChunk]:
    fused_scores: dict[str, float] = {}
    best_result_by_chunk_id: dict[str, RetrievedChunk] = {}

    for results in [vector_results, bm25_results]:
        for result in results:
            fused_scores[result.chunk_id] = fused_scores.get(result.chunk_id, 0.0) + (
                1.0 / (rrf_k + result.rank)
            )

            if result.chunk_id not in best_result_by_chunk_id:
                best_result_by_chunk_id[result.chunk_id] = result

    ranked_chunk_ids = sorted(
        fused_scores,
        key=lambda chunk_id: fused_scores[chunk_id],
        reverse=True,
    )[:top_k]

    fused_results: list[RetrievedChunk] = []

    for rank, chunk_id in enumerate(ranked_chunk_ids, start=1):
        base_result = best_result_by_chunk_id[chunk_id]

        fused_results.append(
            RetrievedChunk(
                chunk_id=base_result.chunk_id,
                paper_id=base_result.paper_id,
                paper_title=base_result.paper_title,
                section_id=base_result.section_id,
                section_title=base_result.section_title,
                raw_text=base_result.raw_text,
                contextual_summary=base_result.contextual_summary,
                score=fused_scores[chunk_id],
                retrieval_method="hybrid_rrf",
                rank=rank,
                page_start=base_result.page_start,
                page_end=base_result.page_end,
            )
        )

    return fused_results

def retrieve_hybrid(
    question: str,
    top_k: int = 5,
    vector_top_k: int = 20,
    bm25_top_k: int = 20,
) -> list[RetrievedChunk]:
    vector_results = retrieve_vector(question, top_k=vector_top_k)
    bm25_results = retrieve_bm25(question, top_k=bm25_top_k)

    return reciprocal_rank_fusion(
        vector_results=vector_results,
        bm25_results=bm25_results,
        top_k=top_k,
    )

def main() -> None:
    question = "What is AutoGraph-R1?"

    print(f"Query: {question}\n")

    results = retrieve_hybrid(question, top_k=5)

    for result in results:
        print(f"Rank {result.rank} | score={result.score:.4f}")
        print(f"chunk_id={result.chunk_id}")
        print(f"paper_title={result.paper_title}")
        print(f"section_title={result.section_title}")
        print(f"retrieval_method={result.retrieval_method}")
        print(f"raw_text preview={result.raw_text[:150]}...\n")

if __name__ == "__main__":
    main()
