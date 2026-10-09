from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct

try:
    from ..qdrant_provider import get_shared_qdrant_client, get_shared_embedding_model
except (ImportError, ValueError):
    try:
        from src.engine.rag.qdrant_provider import get_shared_qdrant_client, get_shared_embedding_model
    except (ImportError, ValueError):
        get_shared_qdrant_client = lambda path="qdrant_data": QdrantClient(path=path)
        get_shared_embedding_model = lambda model="Qwen/Qwen3-Embedding-0.6B", device="cuda": SentenceTransformer(model, device=device)


class DenseIndex:

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

    def embed_chunk(self, chunks):
        texts = [chunk["text"] for chunk in chunks]
        
        embeddings = self.embedding_model.encode(
            texts,
            normalize_embeddings=True
        )
        return embeddings

    def index_chunks(self, chunks, embeddings):

        points = []

        for chunk, embedding in zip(chunks, embeddings):

            point = PointStruct(
                id=chunk["id"],
                vector=embedding.tolist(),
                payload={
                    "text": chunk["text"],
                    "source": chunk["source"],
                    "pages": chunk["pages"],
                    "word_count": chunk["word_count"]
                }
            )

            points.append(point)

        self.qdrant.upsert(
            collection_name=self.collection_name,
            points=points,
            wait=True
        )

if __name__ == "__main__":
    import sys
    from pathlib import Path

    # Add project root to sys.path so direct script execution works
    project_root = Path(__file__).resolve().parents[4]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from src.engine.rag.ingestion.pipeline import IngestionPipeline
    
    pipeline = IngestionPipeline()

    chunks = pipeline.ingest("benchmark_data/aiml.pdf")

    indexer = DenseIndex()

    embeddings = indexer.embed_chunk(chunks)

    print("Chunks:", len(chunks))
    print("Embeddings:", len(embeddings))

    indexer.index_chunks(chunks, embeddings)

    print("Indexing complete.")

    indexer.qdrant.close()