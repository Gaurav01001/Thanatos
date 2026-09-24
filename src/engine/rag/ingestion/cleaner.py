import re


class TextCleaner:

    def clean_page_text(self, text):
        lines = text.split("\n")

        cleaned_lines = []

        for line in lines:
            line = line.strip()

            if not line:
                continue

            if re.match(
                r"^(?:page\s*)?[-—\s]*\d+[-—\s]*$",
                line,
                re.IGNORECASE
            ):
                continue

            if re.match(r"^[\W_]+$", line):
                continue

            line = re.sub(
                r"[\uf0b7\u25a0\ufffd•]",
                " ",
                line
            )

            line = re.sub(
                r"\s+",
                " ",
                line
            ).strip()

            if line:
                cleaned_lines.append(line)

        cleaned_text = " ".join(cleaned_lines)

        return re.sub(
            r"\s+",
            " ",
            cleaned_text
        ).strip()
    

    def clean_page(self, pages):
        clean_pages = []

        for page in pages:
            clean_pages.append({
                "page": page.get("page", page.get("page_num")),
                "text": self.clean_page_text(page["text"])
            })
        return clean_pages

    # Alias to support both singular and plural naming
    clean_pages = clean_page

if __name__ == "__main__":

    # pyrefly: ignore [missing-import]
    from loaders.pdf_loader import pdfLoader

    loader = pdfLoader()
    cleaner = TextCleaner()

    pages = loader.load("benchmark_data/aiml.pdf")
    cleaned_pages = cleaner.clean_page(pages)

    print(f"Total pages: {len(cleaned_pages)}")

    print("\n===== RAW =====")
    print(pages[0]["text"][:500])

    print("\n===== CLEANED =====")
    print(cleaned_pages[0]["text"][:500])