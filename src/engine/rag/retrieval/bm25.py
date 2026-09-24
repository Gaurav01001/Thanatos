import re
from rank_bm25 import BM25Okapi


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

class BM25Retriever:
    def __init__(self, chunks):
        self.chunks = chunks
        tokenized_chunks = [tokenize(chunk["text"]) for chunk in chunks]
        self.bm25 = BM25Okapi(tokenized_chunks)
    
    def retrieve(self, query: str, top_k: int = 10):
        tokenized_query = tokenize(query)

        scores = self.bm25.get_scores(tokenized_query)

        ranked_results = sorted(
            zip(self.chunks, scores),
            key=lambda x: x[1],
            reverse=True
        )

        ranked_results = [
            (chunk, score)
            for chunk, score in ranked_results
            if score > 0
        ]

        return ranked_results[:top_k]


if __name__ == "__main__":
    import sys
    sys.path.append(".")

    from tests.test_chunking import extract_chunks_from_pdf

    chunks = extract_chunks_from_pdf("benchmark_data/aiml.pdf")

    retriever = BM25Retriever(chunks)

    results = retriever.retrieve(
        "What is artificial intelligence?",
        top_k=5
    )

    for chunk, score in results:
        print(
            f"Chunk {chunk['id']} | "
            f"Score {score:.4f} | "
            f"Pages {chunk['pages']}"
        )