from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

# Open local Qdrant database
client = QdrantClient(path="qdrant_data")

# Create our collection
client.create_collection(
    collection_name="thanatos_knowledge",
    vectors_config=VectorParams(
        size=1024,
        distance=Distance.COSINE
    )
)

print("Collection created successfully!")

print(client.get_collections())