# TODO: implement pdf path , extract its pages and return structured raw text
import pymupdf as pdf

class pdfLoader:
    def load(self, filepath):
        doc = pdf.open(filepath)
        pages = []
        for page_index in range(len(doc)):
            page_num = page_index + 1
            page = doc[page_index]
            pages.append(
                {
                    "page": page_num,
                    "page_num": page_num,
                    "text": page.get_text()
                }
            )
        doc.close()
        return pages

PDFLoader = pdfLoader

if __name__ == "__main__":

    loader = pdfLoader()

    pages = loader.load(
        "benchmark_data/aiml.pdf"
    )

    print(f"Total pages: {len(pages)}")

    print("\n===== FIRST PAGE =====")
    print(pages[0]["text"][:1000])