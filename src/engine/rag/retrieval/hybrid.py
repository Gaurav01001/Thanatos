
import sys
from pathlib import Path

# Add project root to sys.path so direct script execution works
project_root = Path(__file__).resolve().parents[4]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Step 1 — Import DenseRetriever and BM25Retriever from their respective modules.
try:
    from .dense import DenseRetriever
    from ..indexing.bm25_index import BM25Index
except (ImportError, ValueError):
    # pyrefly: ignore [missing-import]
    from src.engine.rag.retrieval.dense import DenseRetriever
    # pyrefly: ignore [missing-import]
    from src.engine.rag.indexing.bm25_index import BM25Index

# Step 2 — Create the HybridRetriever class.
class HybridRetriever:
# Step 3 — Create __init__ that accepts an existing DenseRetriever and BM25Index.
    def __init__(self, dense_retriever, bm25_index):
        self.dense_retriever = dense_retriever
        self.bm25_index = bm25_index
            
# Step 5 — Create a retrieve() method that accepts:
#         query
#         top_k
    def retrieve(self, query, top_k=10):

# Step 6 — Inside retrieve(), call DenseRetriever.retrieve()
#         using the user's query.
#         Retrieve enough results for RRF, not just the final top_k.
        dense_results = self.dense_retriever.retrieve(query, top_k*2)

# Step 7 — Inside retrieve(), call BM25Index.search()
#         using the same query.
#         Retrieve enough results for RRF.
        bm25_results = self.bm25_index.search(query, top_k*2)
        
        # Add safety guards for empty results
        if not dense_results and not bm25_results:
            return []
        
         
# Step 8 — Create a dictionary to store the RRF score for each chunk ID.
        rrf_scores = {}
# Step 9 — Create a dictionary mapping Dense retrieval chunk IDs
#         to their ranks. 
        dense_rank_map = {
            result.id: rank
            for rank, result in enumerate(dense_results, 1)
        }

# Step 10 — Create a dictionary mapping BM25 chunk IDs
#          to their ranks.
        bm25_rank_map = {
            chunk["id"]: rank
            for rank, (chunk, score) in enumerate(bm25_results, 1)
        }

# Step 11 — Set RRF_K = 60.
        RRF_K = 60
# Step 12 — Loop through the Dense results.
#          For every chunk, add:
#          1 / (RRF_K + its rank)
#          to that chunk's RRF score.
        for result in dense_results:
            chunk_id = result.id
            rank = dense_rank_map[chunk_id]
            rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0) + 1 / (RRF_K + rank)
# Step 13 — Loop through the BM25 results.
#          For every chunk, add:
#          1 / (RRF_K + its rank)
#          to that chunk's RRF score.
        for chunk, score in bm25_results:
            chunk_id = chunk["id"]
            rank = bm25_rank_map[chunk_id]
            rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0) + 1 / (RRF_K + rank)
# Step 14 — Sort the chunk IDs by their combined RRF scores,
#          highest score first.
        sorted_chunk_ids = sorted(
            rrf_scores,
            key=lambda chunk_id: rrf_scores[chunk_id],
            reverse=True,
        )
# Step 15 — Convert the sorted chunk IDs back into the actual
#          chunk/result objects so the next pipeline stage can use them.

        chunk_map = {
            chunk["id"]: chunk
            for chunk in self.bm25_index.chunks
        }
 
        combined_results = []
        for chunk_id in sorted_chunk_ids:
            chunk = chunk_map.get(chunk_id)
            if chunk is not None:
                combined_results.append((chunk, float(rrf_scores[chunk_id])))

# Step 16 — Return the combined top-K results.
        return combined_results[:top_k]
        
# Step 17 — Add a temporary __main__ test.
if __name__ == "__main__":

    dense_retriever = DenseRetriever()

    bm25_index = BM25Index()
    bm25_index.load()

    hybrid_retriever = HybridRetriever(
        dense_retriever,
        bm25_index
    )

    results = hybrid_retriever.retrieve(
        "What is artificial intelligence?",
        top_k=5
    )

    for chunk, score in results:
        print(
            f"Chunk {chunk['id']} | "
            f"Score {score:.4f} | "
            f"Pages {chunk['pages']}"
        )

    dense_retriever.close()