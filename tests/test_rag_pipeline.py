import sys
from pathlib import Path

# Add project root to sys.path so 'tests' and 'src' can be imported when running script directly
sys.path.append(str(Path(__file__).resolve().parent.parent))

# pyrefly: ignore [missing-import]
from tests.test_chunking import extract_chunks_from_pdf

from src.engine.rag.retrieval.bm25 import BM25Retriever
from src.engine.rag.retrieval.dense import DenseRetriever
from src.engine.rag.retrieval.hybrid import HybridRetriever
from src.engine.rag.retrieval.reranker import Reranker
from src.engine.rag.retrieval.better_context import BetterContext
from src.engine.rag.retrieval.citations import CitationManager
from src.engine.rag.generation import RAGGenerator

pdf_path = "benchmark_data/aiml.pdf"
question = "What is artificial intelligence?"

# 1 chunking
chunks = extract_chunks_from_pdf(pdf_path)

print(f"Total chunks={len(chunks)}")

#2 initiate component
dense_retriever= DenseRetriever()
bm25 = BM25Retriever(chunks)

hybrid_retriever = HybridRetriever(
    dense_retriever,
    bm25
)

reranker = Reranker()
better_context = BetterContext()
citation_manager = CitationManager()
generator = RAGGenerator()

#3 Hybrid retrieval
hybrid_result = hybrid_retriever.retrieve(
    question,
    top_k = 10
)

print("\n===== HYBRID RESULTS =====")

for chunk, score in hybrid_result:
    print(
        f"Chunk {chunk['id']} | "
        f"RRF Score {score:.4f} | "
        f"Pages {chunk['pages']}"
    )

#4 reranking
reranked_results = reranker.rerank(
    question,
    hybrid_result,
    top_k=5
)

print("\n===== RERANKED RESULTS =====")

for (chunk, _), score in reranked_results:
    print(
        f"Chunk {chunk['id']} | "
        f"Reranker Score {score:.4f} | "
        f"Pages {chunk['pages']}"
    )
#5 better context
context, final_chunks = better_context.better_context(
    reranked_results,
    max_words=1200
)

print("\n===== FINAL CHUNKS =====")

for chunk in final_chunks:
    print(
        f"Chunk {chunk['id']} | "
        f"Pages {chunk['pages']}"
    )
#6 source map
structured_context, source_map = (
    better_context.build_structured_context(
        final_chunks
    )
)

print("\n===== SOURCE MAP =====")
print(source_map)

# 7. Citation text
source_text = citation_manager.build_source_text(
    source_map
)

print("\n===== SOURCE TEXT =====")
print(source_text)


# 8. Generate answer
prompt = generator.build_prompt(
    question,
    structured_context,
    source_text
)

answer = generator.generate(prompt)

print("\n===== FINAL ANSWER =====")
print(answer)


# 9. Cleanup
dense_retriever.close()