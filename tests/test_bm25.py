# aiml.pdf
#    ↓
# our improved chunks
#    ↓
# BM25 index
#    ↓
# question
#    ↓
# keyword retrieval
#    ↓
# top-k chunks
# Dense retrieval → semantic understanding
# BM25            → exact keyword matching
import re
import nltk
from nltk.corpus import stopwords
from rank_bm25 import BM25Okapi
# pyrefly: ignore [missing-import]
from test_chunking import extract_chunks_from_pdf

# Ensure stopwords are available
try:
    STOP_WORDS = set(stopwords.words("english"))
except LookupError:
    nltk.download("stopwords", quiet=True)
    STOP_WORDS = set(stopwords.words("english"))


def tokenize(text: str) -> list[str]:
    """
    Domain-aware tokenizer that preserves technical terms (e.g., 'AND-OR', 'A*',
    '8-puzzle', 'if-then') while filtering out standard English stopwords.
    """
    text = text.lower()

    # Pattern to capture compound/technical terms (hyphens, starred algorithms) or standard words
    pattern = r"\b[a-z0-9]+(?:-[a-z0-9]+)+\b|\b[a-z0-9]+\*|\b[a-z0-9]+\b"
    raw_tokens = re.findall(pattern, text)

    tokens = []
    for token in raw_tokens:
        # Preserve technical terms (containing hyphens or asterisks) regardless of component stopwords
        if "-" in token or "*" in token:
            tokens.append(token)
        elif token not in STOP_WORDS:
            tokens.append(token)

    return tokens


if __name__ == "__main__":
    test_queries = [
        "What is artificial intelligence?",
        "Explain AND-OR graphs.",
        "Explain the A* algorithm.",
        "What is the 8-puzzle problem?",
        "Explain if-then rules.",
    ]

    for query in test_queries:
        print(query)
        print(tokenize(query))
        print()
