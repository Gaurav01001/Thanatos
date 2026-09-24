import sys
from pathlib import Path

# Add project root to sys.path so direct script execution works
project_root = Path(__file__).resolve().parents[3]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

try:
    from .generation import RAGGenerator
    from .indexing.bm25_index import BM25Index
    from .indexing.indexer import DocumentIndexer
    from .retrieval.better_context import BetterContext
    from .retrieval.citations import CitationManager
    from .retrieval.dense import DenseRetriever
    from .retrieval.hybrid import HybridRetriever
    from .retrieval.reranker import Reranker
except (ImportError, ValueError):
    # pyrefly: ignore [missing-import]
    # pyrefly: ignore [missing-import]
    from src.engine.rag.generation import RAGGenerator

    # pyrefly: ignore [missing-import]
    from src.engine.rag.indexing.bm25_index import BM25Index
    from src.engine.rag.indexing.indexer import DocumentIndexer

    # pyrefly: ignore [missing-import]
    from src.engine.rag.retrieval.better_context import BetterContext

    # pyrefly: ignore [missing-import]
    from src.engine.rag.retrieval.citations import CitationManager

    # pyrefly: ignore [missing-import]
    from src.engine.rag.retrieval.dense import DenseRetriever

    # pyrefly: ignore [missing-import]
    from src.engine.rag.retrieval.hybrid import HybridRetriever

    # pyrefly: ignore [missing-import]
    from src.engine.rag.retrieval.reranker import Reranker



class RAGManager:

    def __init__(self):
        self.document_indexer = DocumentIndexer()

        self.dense_retriever = DenseRetriever()

        self.bm25_index = BM25Index()
        try:
            self.bm25_index.load()
        except Exception:
            pass

        self.hybrid_retriever = HybridRetriever(
            self.dense_retriever,
            self.bm25_index
        )

        self.reranker = Reranker()

        self.better_context = BetterContext()

        self.citation_manager = CitationManager()

        self.generator = RAGGenerator()
        
    def has_documents(self) -> bool:
        """Returns True if there is at least one indexed chunk in the knowledge base."""
        if hasattr(self, "bm25_index") and hasattr(self.bm25_index, "chunks") and len(self.bm25_index.chunks) > 0:
            return True

        try:
            if hasattr(self, "dense_retriever") and hasattr(self.dense_retriever, "client"):
                colls = self.dense_retriever.client.get_collections().collections
                if any(c.name == "chunks" for c in colls):
                    info = self.dense_retriever.client.get_collection("chunks")
                    return bool(info.points_count and info.points_count > 0)
        except Exception:
            pass

        return False

    def list_indexed_documents(self) -> list[str]:
        """Returns a sorted list of unique document filepaths or sources currently indexed."""
        docs = set()
        if hasattr(self, "bm25_index") and hasattr(self.bm25_index, "chunks"):
            for chunk in self.bm25_index.chunks:
                source = chunk.get("source")
                if source:
                    docs.add(str(source))
        return sorted(docs)

    # Step 9 — Create index_document(filepath) to send a document to DocumentIndexer
    def index_document(self, filepath: str):
        self.document_indexer.index_document(filepath)
        try:
            self.bm25_index.load()
        except Exception:
            pass

    def ask(self, question):
        hybrid_results = self.hybrid_retriever.retrieve(question, top_k=10)
        reranked = self.reranker.rerank(question, hybrid_results, top_k=5)
        _context, final_chunks = self.better_context.better_context(
            reranked
        )
        
        structured_context, source_map = (self.better_context.build_structured_context(final_chunks))
        source_text = self.citation_manager.build_source_text(source_map)

        prompt = self.generator.build_prompt(
            question,
            structured_context,
            source_text
        )

        answer = self.generator.generate(prompt)

        return answer, source_text

    def ask_document(self, question: str):
        return self.ask(question)
    
    def close(self):
        self.dense_retriever.close()


if __name__ == "__main__":

    rag = RAGManager()

    answer, sources = rag.ask(
        "What is artificial intelligence?"
    )

    print("\n===== ANSWER =====")
    print(answer)

    print("\n===== SOURCES =====")
    print(sources)

    rag.close()