# pyrefly: ignore [missing-import]
from docx import Document


class DocxLoader:
    def load(self, filepath):
        document = Document(filepath)

        text = "\n".join(
            paragraph.text
            for paragraph in document.paragraphs
            if paragraph.text.strip()
        )

        return [
            {
                "page": 1,
                "text": text
            }
        ]

docxLoader = DocxLoader


if __name__ == "__main__":

    loader = DocxLoader()

    pages = loader.load("benchmark_data/context.docx")

    print(f"Total pages: {len(pages)}")
    print("\n===== CONTENT =====")
    print(pages[0]["text"][:1000])