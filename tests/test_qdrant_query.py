from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer


COLLECTION_NAME = "thanatos_knowledge"


# Load embedding model
model = SentenceTransformer(
    "Qwen/Qwen3-Embedding-0.6B",
    device="cuda"
)

# Connect to existing Qdrant database
client = QdrantClient(path="qdrant_data")


while True:
    question = input("\nYou: ")

    if question.lower() in ["exit", "quit"]:
        break

    # Convert question into an embedding
    query_vector = model.encode(
        question,
        prompt_name="query",
        normalize_embeddings=True
    )

    # Search Qdrant
    results = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector.tolist(),
        limit=5,
        with_payload=True
    )

    print("\n--- Retrieved Chunks ---")

    for i, result in enumerate(results.points, 1):
        payload = result.payload

        print(f"\n#{i}")
        print(f"Score: {result.score:.4f}")
        print(f"Chunk: {payload['chunk_id']}")
        print(f"Page: {payload['page']}")
        print(f"Text: {payload['text'][:500]}...")


client.close()
print("\nDone.")
