# Take a query → embed it with Qwen3-Embedding-0.6B → search Qdrant → return the top chunks.
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient

try:
    from ..qdrant_provider import get_shared_qdrant_client, get_shared_embedding_model, close_shared_qdrant_client
except (ImportError, ValueError):
    try:
        from src.engine.rag.qdrant_provider import get_shared_qdrant_client, get_shared_embedding_model, close_shared_qdrant_client
    except (ImportError, ValueError):
        get_shared_qdrant_client = lambda path="qdrant_data": QdrantClient(path=path)
        get_shared_embedding_model = lambda model="Qwen/Qwen3-Embedding-0.6B", device="cuda": SentenceTransformer(model, device=device)
        close_shared_qdrant_client = lambda path="qdrant_data": None


class DenseRetriever:
    def __init__(self, qdrant_client=None, embedding_model=None):
        self.embedding_model = (
            embedding_model
            if embedding_model is not None
            else get_shared_embedding_model("Qwen/Qwen3-Embedding-0.6B", device="cuda")
        )

        self.qdrant = (
            qdrant_client
            if qdrant_client is not None
            else get_shared_qdrant_client(path="qdrant_data")
        )
        self.collection_name = "thanatos_hybrid"

    def retrieve(self, query: str, top_k: int = 10):
        query_embedding = self.embedding_model.encode(
            query,
            prompt_name="query",
            normalize_embeddings=True
        )

        results = self.qdrant.query_points(
            collection_name=self.collection_name,
            query=query_embedding.tolist(),
            limit=top_k,
            with_payload=True
        ).points

        return results

    def close(self):
        close_shared_qdrant_client(path="qdrant_data")


if __name__ == "__main__":
    retriever = DenseRetriever()

    results = retriever.retrieve(
        "What is artificial intelligence?",
        top_k=5
    )

    for result in results:
        print(
            f"Chunk {result.id} | "
            f"Score {result.score:.4f} | "
            f"Pages {result.payload['pages']}"
        )

    retriever.close()
