from sentence_transformers import CrossEncoder

reranker = CrossEncoder(
    "cross-encoder/ms-marco-MiniLM-L-6-v2",
    device="cuda"
)

query = "What is artificial intelligence?"

chunks = [
    "Artificial intelligence is the field of study concerned with building machines that can perform tasks that normally require human intelligence.",
    
    "A* is a search algorithm that uses a heuristic function to find an optimal path through a search space.",
    
    "Supervised learning is a machine learning approach where a model learns from labeled training data.",
    
    "Artificial intelligence involves reasoning, learning, problem solving, and decision making."
]

pairs = [(query, chunk) for chunk in chunks]

scores = reranker.predict(pairs)

results = list(zip(chunks, scores))

results.sort(key=lambda x: x[1], reverse=True)

print("\n========== RERANKED RESULTS ==========")

for rank, (chunk, score) in enumerate(results, 1):
    print(f"\nRank {rank} | Score: {score:.4f}")
    print(chunk)

# CrossEncoder
#      ↓
# downloads/loads the pretrained reranker
#      ↓
# GPU (your RTX 3050)