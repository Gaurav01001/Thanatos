from __future__ import annotations

import logging
import math
import sys
from pathlib import Path

logger = logging.getLogger(__name__)
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
        self.is_healthy = True
        self.init_error = None
        self.confidence_threshold = 0.35
        try:
            self.document_indexer = DocumentIndexer()
            self.dense_retriever = DenseRetriever()
            self.bm25_index = BM25Index()
            try:
                self.bm25_index.load()
            except Exception:  # noqa: BLE001, S110
                pass
            self.hybrid_retriever = HybridRetriever(
                self.dense_retriever,
                self.bm25_index,
            )
            self.reranker = Reranker()
            self.better_context = BetterContext()
            self.citation_manager = CitationManager()
            self.generator = RAGGenerator()
        except Exception as e:  # noqa: BLE001
            self.is_healthy = False
            self.init_error = str(e)
            logger.warning("RAGManager initialization degraded: %s. Operating in chat-only fallback mode.", e)
        
    def has_documents(self) -> bool:
        """Returns True if there is at least one indexed chunk in the knowledge base."""
        if not self.is_healthy:
            return False

        if hasattr(self, "bm25_index") and hasattr(self.bm25_index, "chunks") and len(self.bm25_index.chunks) > 0:
            return True

        try:
            if hasattr(self, "dense_retriever") and hasattr(self.dense_retriever, "client"):
                colls = self.dense_retriever.client.get_collections().collections
                if any(c.name == "chunks" for c in colls):
                    info = self.dense_retriever.client.get_collection("chunks")
                    return bool(info.points_count and info.points_count > 0)
        except Exception:  # noqa: BLE001, S110
            pass

        return False

    def list_indexed_documents(self) -> list[str]:
        """Returns a sorted list of unique document filepaths or sources currently indexed."""
        if not self.is_healthy:
            return []

        docs = set()
        if hasattr(self, "bm25_index") and hasattr(self.bm25_index, "chunks"):
            for chunk in self.bm25_index.chunks:
                source = chunk.get("source")
                if source:
                    docs.add(str(source))
        return sorted(docs)

    # Step 9 — Create index_document(filepath) to send a document to DocumentIndexer
    def index_document(self, filepath: str):
        if not self.is_healthy:
            return f"Error indexing document: RAG subsystem is degraded ({self.init_error})."
        self.document_indexer.index_document(filepath)
        try:
            self.bm25_index.load()
        except Exception:  # noqa: BLE001, S110
            pass

    def ask(self, question: str, confidence_threshold: float | None = None):
        # 1. Health guard: if RAG components failed to load, fall back gracefully
        if not self.is_healthy:
            logger.warning("RAGManager.ask called while degraded (%s). Falling back to pure chat.", self.init_error)
            fallback_prompt = f"""You are Thanatos, a direct, concise AI assistant.
The user asked: "{question}"
Document search is currently unavailable ({self.init_error or 'resource limitation'}).
Answer the question directly and helpfully using your general knowledge, and mention that document lookup is temporarily unavailable.

Answer:"""
            answer = getattr(self, "generator", RAGGenerator()).generate(fallback_prompt)
            return answer, None

        threshold = confidence_threshold if confidence_threshold is not None else self.confidence_threshold

        hybrid_results = self.hybrid_retriever.retrieve(question, top_k=10)
        reranked = self.reranker.rerank(question, hybrid_results, top_k=5)

        # Calculate top retrieval confidence score
        top_confidence = 0.0
        if reranked:
            top_logit = reranked[0][1]  # rerank score
            # Safe sigmoid computation
            if top_logit > 20:
                top_confidence = 1.0
            elif top_logit < -20:
                top_confidence = 0.0
            else:
                top_confidence = 1.0 / (1.0 + math.exp(-float(top_logit)))

        # Fallback if no relevant evidence exists in indexed documents
        if not reranked or top_confidence < threshold:
            fallback_prompt = f"""You are Thanatos, a direct, concise AI assistant.
The user asked: "{question}"
You searched their indexed documents, but found no relevant information or direct evidence about this topic.
1. State clearly and concisely that the indexed documents do not mention or cover this topic.
2. If applicable, answer the question helpfully using your general knowledge.
3. Do not invent citations or source tags.

Answer:"""
            fallback_answer = self.generator.generate(fallback_prompt)
            return fallback_answer, None

        _context, final_chunks = self.better_context.better_context(reranked)
        structured_context, source_map = self.better_context.build_structured_context(final_chunks)
        source_text = self.citation_manager.build_source_text(source_map)

        prompt = self.generator.build_prompt(
            question,
            structured_context,
            source_text,
        )

        answer = self.generator.generate(prompt)
        filtered_source_text = self.citation_manager.filter_unused_citations(
            answer=answer,
            source_map=source_map,
            source_text=source_text,
        )
        return answer, filtered_source_text

    def ask_document(self, question: str):
        return self.ask(question)
    
    def close(self):
        if hasattr(self, "dense_retriever") and hasattr(self.dense_retriever, "close"):
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