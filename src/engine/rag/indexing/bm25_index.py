import re
import nltk
from nltk.corpus import stopwords
from rank_bm25 import BM25Okapi
import pickle
try:
    STOP_WORDS = set(stopwords.words("english"))
except LookupError:
    nltk.download("stopwords", quiet=True)
    STOP_WORDS = set(stopwords.words("english"))

class BM25Index:
    def __init__(self):
        self.bm25 = None

        self.chunks = []

    def _tokenize(self, text: str)-> list[str]:
        
        pattern = r"\b[a-z0-9]+(?:-[a-z0-9]+)+\b|\b[a-z0-9]+\*|\b[a-z0-9]+\b"
        raw_tokens = re.findall(pattern, text.lower())

        tokens = []
        for token in raw_tokens:
            if "-" in token or "*" in token:
                tokens.append(token)
            elif token not in STOP_WORDS:
                tokens.append(token)
        return tokens

    def build(self, chunks):
        self.chunks = chunks

        tokenized_corpus = [
            self._tokenize(chunk["text"]) 
            for chunk in chunks
        ]

        self.bm25 = BM25Okapi(tokenized_corpus)

        print("BM25 index built.")
    
    def search(self, query: str, top_k: int = 10):
        if self.bm25 is None:
            raise ValueError("BM25 index has not been built yet. Call build() first.")

        query_tokens = self._tokenize(query)
        scores = self.bm25.get_scores(query_tokens)
        top_indices = scores.argsort()[::-1][:top_k]
        result = []

        for index in top_indices:
            result.append(
                (self.chunks[index], scores[index])
            )

        return result
    def save(self, filepath="bm25_index.pkl"):
        with open(filepath, "wb") as file:
            pickle.dump(
                {
                    "bm25": self.bm25,
                    "chunks": self.chunks,
                    
                },
                file
            )

        print(f"BM25 index saved to {filepath}") 

    def load(self, filepath = "bm25_index.pkl"):

        with open(filepath, "rb") as file:
            data = pickle.load(file)
        self.bm25 = data["bm25"]
        self.chunks = data["chunks"]
        print(f"BM25 index loaded from {filepath}")

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

    index = BM25Index()

    index.load()

    print("Chunks:", len(index.chunks))

    results = index.search(
        "What is artificial intelligence?",
        top_k=5
    )

    for chunk, score in results:
        print(
            f"Chunk {chunk['id']} | "
            f"Score {score:.4f} | "
            f"Pages {chunk['pages']}"
        )
