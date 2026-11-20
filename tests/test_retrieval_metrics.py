from sentence_transformers import SentenceTransformer, util

model = SentenceTransformer(
    "Qwen/Qwen3-Embedding-0.6B",
    device="cuda"
)

# These represent chunks that might have come from real documents.
chunks = [
    "Gradient descent iteratively changes the parameters of a machine learning model "
    "in order to reduce the objective or loss function.",

    "Embeddings represent text as numerical vectors. Text with related meanings tends "
    "to occupy nearby regions of the embedding space.",

    "A vector database stores embedding vectors together with their associated text "
    "and metadata and allows similarity-based retrieval.",

    "Retrieval augmented generation retrieves relevant external information and gives "
    "that information to a language model as context before generating an answer.",

    "Python is a general-purpose programming language commonly used for web development, "
    "automation, data science, and machine learning.",

    "A GPU performs many numerical operations in parallel and can accelerate neural "
    "network inference and training.",

    "Cosine similarity measures the directional similarity between two vectors and is "
    "commonly used when comparing text embeddings.",

    "Chunking divides a large document into smaller pieces so that relevant sections "
    "can be retrieved instead of providing the entire document to the language model.",

    "BM25 is a lexical information-retrieval method that ranks documents according to "
    "the occurrence and importance of query terms.",

    "Qdrant is a vector database designed for storing and searching vector embeddings."
]


# expected_indices contains every chunk that is considered relevant.
#
# Multiple relevant chunks are allowed.
tests = [

    {
        "question": "How does an optimizer know which way to change the weights?",
        "expected_indices": [0],
    },

    {
        "question": "How are meanings represented numerically for semantic search?",
        "expected_indices": [1],
    },

    {
        "question": "Where can the numerical representations of documents be stored and searched?",
        "expected_indices": [2, 9],
    },

    {
        "question": "How can a language model answer using information that was not inside its original training data?",
        "expected_indices": [3],
    },

    {
        "question": "What programming language could I use to build automation and machine learning tools?",
        "expected_indices": [4],
    },

    {
        "question": "Why can my graphics card make neural-network calculations faster?",
        "expected_indices": [5],
    },

    {
        "question": "How can I determine whether two embedding vectors point in a similar direction?",
        "expected_indices": [6],
    },

    {
        "question": "Why don't we send an entire 500-page book to the LLM at once?",
        "expected_indices": [7],
    },

    {
        "question": "How can a search system find documents containing important words from my query?",
        "expected_indices": [8],
    },

    {
        "question": "I want a system that searches stored embeddings efficiently. What technology could I use?",
        "expected_indices": [2, 9],
    },
]


# Create embeddings for all document chunks once.
chunk_embeddings = model.encode(
    chunks,
    normalize_embeddings=True
)


def evaluate_recall(k):
    hits = 0

    for test in tests:

        question = test["question"]
        expected = set(test["expected_indices"])

        query_embedding = model.encode(
            question,
            normalize_embeddings=True
        )

        scores = util.cos_sim(
            query_embedding,
            chunk_embeddings
        )[0]

        ranked_indices = scores.argsort(
            descending=True
        ).tolist()

        top_k = ranked_indices[:k]

        # A test is considered successful if at least one
        # expected relevant chunk appears in the top K.
        found = any(index in expected for index in top_k)

        hits += int(found)

        print("\nQuestion:")
        print(question)

        print("Expected:", [i + 1 for i in expected])
        print("Top", k, ":", [i + 1 for i in top_k])

        print("Retrieved relevant chunk:", found)

        # Show the scores of the top results.
        print("Scores:")

        for index in top_k:
            print(
                f"  Chunk {index + 1}: "
                f"{scores[index].item():.4f}"
            )

    return hits / len(tests)


print("\n==============================")
print("QWEN3 EMBEDDING RETRIEVAL TEST")
print("==============================")

recall_1 = evaluate_recall(1)
recall_3 = evaluate_recall(3)
recall_5 = evaluate_recall(5)

print("\n==============================")
print(f"Recall@1: {recall_1:.2%}")
print(f"Recall@3: {recall_3:.2%}")
print(f"Recall@5: {recall_5:.2%}")
print("==============================")