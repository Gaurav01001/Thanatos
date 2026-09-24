import sys
from pathlib import Path

# Add project root to sys.path so direct script execution works
project_root = Path(__file__).resolve().parents[4]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

try:
    from ..ingestion.pipeline import IngestionPipeline
    from .dense_index import DenseIndex
    from .bm25_index import BM25Index
except (ImportError, ValueError):
    # pyrefly: ignore [missing-import]
    from src.engine.rag.ingestion.pipeline import IngestionPipeline
    # pyrefly: ignore [missing-import]
    from src.engine.rag.indexing.dense_index import DenseIndex
    # pyrefly: ignore [missing-import]
    from src.engine.rag.indexing.bm25_index import BM25Index


class DocumentIndexer:
    
    def close(self):
        self.dense_indexer.qdrant.close()
    
    def __init__(self):
        self.pipeline = IngestionPipeline()
        self.dense_indexer = DenseIndex()
        self.bm25_index = BM25Index()

    def index_document(self, pdf_path):
        chunks = self.pipeline.ingest(pdf_path)

        #create embeddings for dense index
        embeddings = self.dense_indexer.embed_chunk(chunks)

        #put vectors into qdrant
        self.dense_indexer.index_chunks(chunks, embeddings)

        #build bm25 index
        self.bm25_index.build(chunks)

        #save bm25 index
        self.bm25_index.save()

if __name__ == "__main__":

    indexer = DocumentIndexer()

    indexer.index_document(
        "benchmark_data/aiml.pdf"
    )

    print("Document indexing complete.")
    
    indexer.close()