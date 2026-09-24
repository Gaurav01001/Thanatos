import os
import sys
from pathlib import Path

# Add project root to sys.path so direct script execution works
project_root = Path(__file__).resolve().parents[4]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.engine.rag.ingestion.loaders.pdf_loader import PDFLoader, pdfLoader
from src.engine.rag.ingestion.loaders.txt_loader import TXTLoader, txtLoader
from src.engine.rag.ingestion.loaders.md_loader import MDLoader, mdLoader
from src.engine.rag.ingestion.loaders.docx_loader import DocxLoader, docxLoader
from src.engine.rag.ingestion.cleaner import TextCleaner
from src.engine.rag.ingestion.chunker import TextChunker

class IngestionPipeline:

    def __init__(self):
        self.loaders = {
            ".pdf": PDFLoader(),
            ".txt": TXTLoader(),
            ".md": MDLoader(),
            ".docx": DocxLoader()
        }

        self.cleaner = TextCleaner()
        self.chunker = TextChunker()

    def ingest(self, filepath):
        extension = os.path.splitext(filepath)[1].lower()

        if extension not in self.loaders:
            raise ValueError(f"Unsupported file type: {extension}")

        loader = self.loaders[extension]

        pages = loader.load(filepath)

        cleaned_pages = self.cleaner.clean_pages(pages)

        chunks = self.chunker.chunk(
            cleaned_pages,
            source=filepath
        )

        return chunks

if __name__ == "__main__":

    pipeline = IngestionPipeline()

    chunks = pipeline.ingest("benchmark_data/aiml.pdf")

    print(f"Total chunks: {len(chunks)}")

    print("\n===== FIRST CHUNK =====")
    print(chunks[0])

    print("\n===== LAST CHUNK =====")
    print(chunks[-1])