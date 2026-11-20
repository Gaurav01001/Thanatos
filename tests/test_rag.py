from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer
import ollama


COLLECTION_NAME = "thanatos_knowledge"


# -----------------------------
# 1. Load embedding model
# -----------------------------

print("Loading embedding model...")

embedding_model = SentenceTransformer(
    "Qwen/Qwen3-Embedding-0.6B",
    device="cuda"
)


# -----------------------------
# 2. Connect to Qdrant
# -----------------------------

client = QdrantClient(path="qdrant_data")


# -----------------------------
# 3. Ask the user
# -----------------------------

question = input("\nYou: ")


# -----------------------------
# 4. Embed the question
# -----------------------------

query_vector = embedding_model.encode(
    question,
    prompt_name="query",
    normalize_embeddings=True
)


# -----------------------------
# 5. Retrieve relevant chunks
# -----------------------------

results = client.query_points(
    collection_name=COLLECTION_NAME,
    query=query_vector.tolist(),
    limit=5,
    with_payload=True
)

client.close()


# -----------------------------
# 6. Build context
# -----------------------------

context_parts = []

for result in results.points:

    payload = result.payload

    context_parts.append(
        f"""
Source: {payload['source']}
Page: {payload['page']}

{payload['text']}
"""
    )


context = "\n\n---\n\n".join(context_parts)


# -----------------------------
# 7. Build RAG prompt
# -----------------------------

prompt = f"""
You are Thanatos, a helpful AI assistant.

Answer the user's question using ONLY the information
provided in the context below.

If the context does not contain enough information to
answer the question, say that the information was not
found in the provided documents.

Do not invent facts.

Context:
{context}

User question:
{question}

Answer clearly and concisely.
"""


# -----------------------------
# 8. Generate answer
# -----------------------------

response = ollama.chat(
    model="qwen2.5-coder:7b",
    messages=[
        {
            "role": "user",
            "content": prompt
        }
    ]
)


# -----------------------------
# 9. Show answer
# -----------------------------

print("\nThanatos:")
print(response["message"]["content"])