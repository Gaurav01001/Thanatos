from nltk.tokenize import sent_tokenize


class TextChunker:

    def __init__(
        self,
        max_words=300,
        overlap_words=50,
        min_page_words=5
    ):
        self.max_words = max_words
        self.overlap_words = overlap_words
        self.min_page_words = min_page_words

    def chunk(self, pages, source):

        raw_chunks = []
        current_chunk = []
        current_word_count = 0

        for page in pages:

            page_number = page["page"]
            text = page["text"]

            words = [
                word
                for word in text.split()
                if any(c.isalpha() for c in word)
            ]

            if len(words) < self.min_page_words:
                continue

            sentences = sent_tokenize(text)

            for sentence in sentences:

                word_count = len(sentence.split())

                if (
                    current_word_count + word_count
                    <= self.max_words
                ):
                    current_chunk.append(
                        (page_number, sentence)
                    )
                    current_word_count += word_count

                else:

                    if current_chunk:
                        raw_chunks.append(
                            current_chunk.copy()
                        )

                    overlap_sentences = []
                    overlap_word_count = 0

                    for page_num, sentence_text in reversed(
                        current_chunk
                    ):
                        overlap_word_count += len(
                            sentence_text.split()
                        )

                        overlap_sentences.insert(
                            0,
                            (page_num, sentence_text)
                        )

                        if (
                            overlap_word_count
                            >= self.overlap_words
                        ):
                            break

                    current_chunk = (
                        overlap_sentences
                        + [(page_number, sentence)]
                    )

                    current_word_count = (
                        overlap_word_count
                        + word_count
                    )

        if current_chunk:
            raw_chunks.append(
                current_chunk.copy()
            )

        structured_chunks = []

        for chunk_id, raw_chunk in enumerate(
            raw_chunks,
            start=1
        ):

            pages_used = sorted(
                set(
                    page_number
                    for page_number, _ in raw_chunk
                )
            )

            chunk_text = " ".join(
                sentence
                for _, sentence in raw_chunk
            )

            structured_chunks.append({
                "id": chunk_id,
                "text": chunk_text,
                "pages": pages_used,
                "word_count": len(chunk_text.split()),
                "source": source
            })

        return structured_chunks
if __name__ == "__main__":

    # pyrefly: ignore [missing-import]
    from loaders.pdf_loader import pdfLoader
    # pyrefly: ignore [missing-import]
    from cleaner import TextCleaner

    loader = pdfLoader()
    cleaner = TextCleaner()
    chunker = TextChunker()

    pages = loader.load(
        "benchmark_data/aiml.pdf"
    )

    cleaned_pages = cleaner.clean_pages(pages)

    chunks = chunker.chunk(
        cleaned_pages,
        "benchmark_data/aiml.pdf"
    )

    print(f"Total chunks: {len(chunks)}")

    print("\n===== FIRST CHUNK =====")
    print(chunks[0])

    print("\n===== LAST CHUNK =====")
    print(chunks[-1])