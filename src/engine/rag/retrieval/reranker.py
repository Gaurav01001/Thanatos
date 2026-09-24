from sentence_transformers import CrossEncoder


class Reranker:
    def __init__(self):
        # Load CrossEncoder model on CUDA
        self.model = CrossEncoder(
            "cross-encoder/ms-marco-MiniLM-L6-v2",
            device="cuda"
        )

    # Create rerank method
    def rerank(self, query, result, top_k=5):
        if not result:
            return []

        pairs = [
            (query, chunk["text"])
            for chunk, _ in result
        ]

        scores = self.model.predict(pairs)

        reranked = sorted(
            zip(result, scores),
            key=lambda x: x[1],
            reverse=True
        )

        return reranked[:top_k]


if __name__ == "__main__":
    import sys
    sys.path.append(".")

    try:
        from .better_context import BetterContext
        from .bm25 import BM25Retriever
        from .dense import DenseRetriever
        from .hybrid import HybridRetriever
    except ImportError:
        # pyrefly: ignore [missing-import]
        # pyrefly: ignore [missing-import]
        from better_context import BetterContext

        # pyrefly: ignore [missing-import]
        from bm25 import BM25Retriever
        from dense import DenseRetriever

        # pyrefly: ignore [missing-import]
        from hybrid import HybridRetriever
    # pyrefly: ignore [missing-import]
    from tests.test_chunking import extract_chunks_from_pdf

    # 1. Load chunks
    chunks = extract_chunks_from_pdf("benchmark_data/aiml.pdf")

    # 2. Create retrievers & reranker
    dense_retriever = DenseRetriever()
    bm25_retriever = BM25Retriever(chunks)
    hybrid_retriever = HybridRetriever(dense_retriever, bm25_retriever)
    reranker = Reranker()

    # 3. Get hybrid results
    query = "What is artificial intelligence?"
    hybrid_results = hybrid_retriever.retrieve(query, top_k=10)

    # 4. Pass results to Reranker
    reranked_results = reranker.rerank(query, hybrid_results, top_k=5)

    #4.5 Extract chunks
    better_context = BetterContext()
    context, final_chunks = better_context.better_context(
        reranked_results,
        max_words=1200
    )
    # 5. Print reranked chunks and scores
    # for (chunk, _), score in reranked_results:
    #     print(
    #         f"Chunk {chunk['id']} | "
    #         f"Score {score:.4f} | "
    #         f"Pages {chunk['pages']}"
    #     )
    # print("\nBetter Context:")
    # print(context)
    structured_context, source_map = better_context.build_structured_context(
        final_chunks
)

    print("\n===== SOURCE MAP =====")
    print(source_map)
    # 6. Close the dense retriever
    dense_retriever.close()

