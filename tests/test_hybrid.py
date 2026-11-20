import re
import sys
import numpy as np
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct
from sentence_transformers import CrossEncoder

if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# pyrefly: ignore [missing-import]
from test_chunking import extract_chunks_from_pdf

chunks = extract_chunks_from_pdf("benchmark_data/aiml.pdf")

# print(f"Total chunks: {len(chunks)}")

#2 build BM25 index

STOP_WORDS = {
    "a", "an", "the", "is", "are", "was", "were",
    "what", "which", "who", "how", "why",
    "of", "to", "in", "on", "for", "with",
    "and", "or", "as", "by", "from", "this",
    "that", "these", "those"
}


def tokenize(text: str) -> list[str]:
    """
    Tokenize text while preserving technical terms
    and removing common stopwords.
    """

    text = text.lower()

    pattern = r"\b[a-z0-9]+(?:-[a-z0-9]+)+\b|\b[a-z0-9]+\*|\b[a-z0-9]+\b"

    tokens = re.findall(pattern, text)

    tokens = [
        token for token in tokens
        if token not in STOP_WORDS
    ]

    return tokens

tokenized_chunks = [tokenize(chunk["text"]) for chunk in chunks]

bm25 = BM25Okapi(tokenized_chunks)
# 184 chunks
#    ↓
# tokenize each chunk
#    ↓
# 184 lists of tokens
#    ↓
# BM25Okapi
#    ↓
# BM25 index

#3 Qwen3 embedding model + Qdrant.
embedding_model = SentenceTransformer(
    "Qwen/Qwen3-Embedding-0.6B",
    device="cuda"
)

reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L6-v2", device="cuda")

qdrant = QdrantClient(path="qdrant_data")

#4 create a frest qdrant collection for the improved chunks

COLLECTION_NAME = "thanatos_hybrid" #collection name

if qdrant.collection_exists(COLLECTION_NAME): #check if collection already exists
    qdrant.delete_collection(COLLECTION_NAME)#delete if exists

qdrant.create_collection( #create a new collection
    collection_name=COLLECTION_NAME, #collection name
    vectors_config={ #vector configuration this line is telling qdrant to use the same vector size as the embedding model
        "size": embedding_model.get_embedding_dimension(), #vector size
        "distance": "Cosine" #cosine similarity
    }
)

#5 we'll embed those exact 184 chunks and put them into this collection
vector_size = embedding_model.get_embedding_dimension() 

print(f"Vector Size: {vector_size}")
print("Embedding chunk...")

pairs = []

for chunk in chunks:
    embedding = embedding_model.encode(
    chunk["text"],
    normalize_embeddings=True
)
    pairs.append({
        "id": chunk["id"],
        "text": chunk["text"],
        "pages": chunk["pages"],
        "source": chunk["source"],
        "embedding": embedding.tolist()
    })

print(f"Embedded chunks: {len(pairs)}")


# 6. Upload vectors to Qdrant

points = []

for item in pairs:
    points.append(
        PointStruct(
            id=item["id"],
            vector=item["embedding"],
            payload={
                "text": item["text"],
                "pages": item["pages"],
                "source": item["source"],
            },
        )
    )

qdrant.upsert(
    collection_name=COLLECTION_NAME,
    points=points,
)

print(f"Uploaded {len(points)} vectors to Qdrant")

# 7verify qdrant collection
collection_info = qdrant.get_collection(COLLECTION_NAME)
print(f"Qdrant points: {collection_info.points_count}")

#8 retrieve using both dense retrieval and BM25

test_queries = [
    "What is artificial intelligence?",
    # "Explain AND-OR graphs.",
    # "Explain the A* algorithm.",
    # "What is the 8-puzzle problem?",
    # "What is supervised learning?",
]

for query in test_queries:
    print(f"\n==========================================")
    print(f"Query: {query}")
    print(f"==========================================")

    # bm25

    tokenized_query = tokenize(query)
    bm25_scores = bm25.get_scores(tokenized_query)

    bm25_result = [
        (chunk, score)
        for chunk, score in zip(chunks, bm25_scores)
        if score > 0 # only include chunks with a score > 0
    ]

    bm25_result.sort(key=lambda x: x[1], reverse=True)
    bm25_result = bm25_result[:10]
    #dense retrieval

    query_embedding = embedding_model.encode(
        query,
        prompt_name="query",
        normalize_embeddings=True
    )

    dense_results = qdrant.query_points(
        collection_name=COLLECTION_NAME,
        query=query_embedding.tolist(),
        limit=10,
        with_payload=True
    ).points

    # print("\n========== BM25 RESULTS ==========")

    # for rank, (chunk, score) in enumerate(bm25_result, 1):
    #     print(
    #         f"Rank {rank} | "
    #         f"Chunk {chunk['id']} | "
    #         f"Score: {score:.4f} | "
    #         f"Pages: {chunk['pages']}"
    #     )


    # print("\n========== DENSE RESULTS ==========")

    # for rank, result in enumerate(dense_results, 1):
    #     print(
    #         f"Rank {rank} | "
    #         f"Chunk {result.id} | "
    #         f"Score: {result.score:.4f} | "
    #         f"Pages: {result.payload['pages']}"
    #     )

    #9 prepare rank with RRf

    bm25_ranks = {chunk["id"] : rank
        for rank, (chunk, score) in enumerate(bm25_result, 1) 
    } 
    dense_ranks = {
        result.id: rank
        for rank, result in enumerate(dense_results, 1)

    }

    # print("\nBM25 ranking:", bm25_ranks)
    # print("Dense ranking:", dense_ranks)

    # 10. Reciprocal Rank Fusion (RRF)

    RRF_K = 60

    rrf_scores = {}

    for chunk_id, rank in bm25_ranks.items():
        rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0) + 1 / (RRF_K + rank)

    for chunk_id, rank in dense_ranks.items():
        rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0) + 1 / (RRF_K + rank)

    hybrid_results = sorted(
        rrf_scores.items(),
        key=lambda x: x[1],
        reverse=True
    )
    # 11. Rerank hybrid candidates
    candidate_id = [chunk_id for chunk_id, _ in hybrid_results[:10]]

    candidate_chunks = [c for c in chunks if c["id"] in candidate_id]

    reranker_pairs = [(query, c["text"]) for c in candidate_chunks]

    reranker_scores = reranker.predict(reranker_pairs)

    reranker_result = list(zip(candidate_chunks, reranker_scores))

    # 11.5 remove redundancy with semantic similarity
    embedding_by_id = {
        item["id"]: np.array(item["embedding"])
        for item in pairs
    }

    reranker_result.sort(key=lambda x: x[1], reverse=True)
    REDUNDANCY_THRESHOLD = 0.75 
 
    kept_chunks = [] 

    for chunk, score in reranker_result[:5]:
        chunk_embedding = embedding_by_id[chunk["id"]]

        is_redundant = False

        for kept in kept_chunks:
            kept_embedding = embedding_by_id[kept["id"]]

            similarity = chunk_embedding @ kept_embedding

            print(
                f"Comparing Chunk {chunk['id']} "
                f"with Chunk {kept['id']} "
                f"→ similarity: {similarity:.4f}"
            )

            if similarity >= REDUNDANCY_THRESHOLD:
                is_redundant = True
                break

        if not is_redundant:
            kept_chunks.append(chunk)

    source_map = {}

    for source_id, chunk in enumerate(kept_chunks, 1):
        source_map[source_id] = {
            "chunk_id" : chunk["id"],
            "source" : chunk["source"],
            "pages" : chunk["pages"],
            }
        
# example of source map
# source_map {
#     "1": {
#         "chunk_id": 2,
#         "source": "benchmark_data/aiml.pdf",
#         "pages": [2, 3]
#     }
# }
    # 12. Build context
    MAX_CONTEXT_WORDS = 1200
    context_parts = []
    context_word_count = 0
    
    for rank, chunk in enumerate(kept_chunks, 1):
        chunk_word_count = len(chunk["text"].split())

        if context_word_count + chunk_word_count > MAX_CONTEXT_WORDS:
            break

        context_parts.append(
            f"===== SOURCE {rank} =====\n"
            f"Source ID: {rank}\n"
            f"File: {chunk['source']}\n"
            f"Pages: {chunk['pages']}\n\n"
            f"{chunk['text']}"
    )

        context_word_count += chunk_word_count

    context = "\n\n".join(context_parts)

    print(f"Reranked chunks: {len(reranker_result[:5])}")
    print(f"Kept after redundancy filtering: {len(kept_chunks)}")
    print("\n========== FINAL CONTEXT ==========")
    print(context)

    # print("\n========== RERANKED RESULTS ==========")

    # for rank, (chunk, score) in enumerate(reranker_result[:5], 1):
    #     print(
    #         f"\nRank {rank} | "
    #         f"Chunk {chunk['id']} | "
    #         f"Score: {score:.4f} | "
    #         f"Pages: {chunk['pages']}"
    #     )
    #     print(f"Text: {chunk['text']}")

qdrant.close()


# Reranked Top 5
#       ↓
# Take highest-ranked chunk
#       ↓
# Compare it with chunks already kept
#       ↓
# Too similar? → discard
# Different enough? → keep
#       ↓
# Final context