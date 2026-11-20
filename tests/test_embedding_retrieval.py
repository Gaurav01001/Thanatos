from sentence_transformers import SentenceTransformer, util

model = SentenceTransformer(
    "Qwen/Qwen3-Embedding-0.6B",
    device="cuda"
)

chunks = [
    "Embeddings convert text into numerical vectors that capture semantic information.",
    "A vector database stores embeddings and allows efficient similarity search.",
    "RAG retrieves relevant information and provides it to an LLM as context.",
    "Gradient descent is an optimization algorithm used to minimize a loss function.",
    "Python is a general-purpose programming language widely used in software development.",
    "An RTX 3050 is an NVIDIA graphics processing unit designed for computers and laptops.",
]

question = "Why do we use embeddings in a RAG system?"

# Convert document chunks into vectors
chunk_embeddings = model.encode(
    chunks,
    normalize_embeddings=True
)

# Convert the question into a vector
question_embedding = model.encode(
    question,
    normalize_embeddings=True
)

# Compare question against every chunk
scores = util.cos_sim(
    question_embedding,
    chunk_embeddings
)[0]

# Rank chunks from most relevant to least relevant
results = sorted(
    zip(scores.tolist(), chunks),
    reverse=True
)

print("\nQuestion:")
print(question)

print("\nRetrieval results:\n")

for rank, (score, chunk) in enumerate(results, start=1):
    print(f"{rank}. Score: {score:.4f}")
    print(f"   {chunk}\n")