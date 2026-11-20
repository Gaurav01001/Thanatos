import re
from typing import List, Dict, Any
import pymupdf as pdf
from nltk.tokenize import sent_tokenize


def clean_page_text(text: str) -> str:
    """Cleans raw PDF page text by removing page numbers, artifacts, and noise."""
    lines = text.split("\n")
    cleaned_lines = []

    for line in lines:
        line = line.strip()

        # Remove standalone page numbers (e.g. "59", "Page 50", "- 12 -")
        if not line or re.match(
            r"^(?:page\s*)?[-—\s]*\d+[-—\s]*$",
            line,
            re.IGNORECASE,
        ):
            continue

        # Remove standalone punctuation or bullet artifacts
        if re.match(r"^[\W_]+$", line):
            continue

        # Clean non-standard bullet symbols and normalize whitespace
        line = re.sub(r"[\uf0b7\u25a0\ufffd•]", " ", line)
        line = re.sub(r"\s+", " ", line).strip()

        if line:
            cleaned_lines.append(line)

    cleaned_text = " ".join(cleaned_lines)
    return re.sub(r"\s+", " ", cleaned_text).strip()


def extract_chunks_from_pdf(
    pdf_path: str,
    max_words: int = 300,
    overlap_words: int = 50,
    min_page_words: int = 5,
) -> List[Dict[str, Any]]:
    """
    Extracts sentence-aware, cross-page chunks from a PDF.

    Returns:
        List of dicts with keys:
        - "id": int (1-based index)
        - "text": str (full chunk text)
        - "pages": List[int] (sorted list of pages covered)
        - "word_count": int (number of words in chunk)
        - "source": str (path to source PDF)
    """
    doc = pdf.open(pdf_path)

    raw_chunks: List[List[tuple]] = []
    current_chunk: List[tuple] = []
    current_word_count = 0

    for page_number, page in enumerate(doc, start=1):
        raw_text = page.get_text()
        cleaned_text = clean_page_text(raw_text)

        # Skip pages with almost no meaningful prose
        words = [w for w in cleaned_text.split() if any(c.isalpha() for c in w)]
        if len(words) < min_page_words:
            continue

        sentences = sent_tokenize(cleaned_text)

        for s in sentences:
            word_count = len(s.split())

            if current_word_count + word_count <= max_words:
                current_chunk.append((page_number, s))
                current_word_count += word_count
            else:
                if current_chunk:
                    raw_chunks.append(current_chunk.copy())

                # Create ~overlap_words sentence overlap
                overlap_sentences = []
                overlap_word_count = 0

                for c in reversed(current_chunk):
                    page_num, sentence_text = c
                    overlap_word_count += len(sentence_text.split())
                    overlap_sentences.insert(0, c)

                    if overlap_word_count >= overlap_words:
                        break

                current_chunk = overlap_sentences + [(page_number, s)]
                current_word_count = overlap_word_count + word_count

    # Add final trailing chunk after the entire document is processed
    if current_chunk:
        raw_chunks.append(current_chunk.copy())

    doc.close()

    # Format structured output
    structured_chunks = []
    for idx, raw in enumerate(raw_chunks, start=1):
        pages = sorted(set(page for page, _ in raw))
        chunk_text = " ".join(sentence for _, sentence in raw)
        word_count = len(chunk_text.split())

        structured_chunks.append({
            "id": idx,
            "text": chunk_text,
            "pages": pages,
            "word_count": word_count,
            "source": pdf_path,
        })

    return structured_chunks


if __name__ == "__main__":
    pdf_path = "benchmark_data/aiml.pdf"
    chunks = extract_chunks_from_pdf(pdf_path)

    word_counts = [c["word_count"] for c in chunks]
    small_chunks = [c for c in chunks if c["word_count"] < 100]
    cross_page_chunks = [c for c in chunks if len(c["pages"]) > 1]

    print(f"Total chunks: {len(chunks)}")
    print(f"Minimum words: {min(word_counts)}")
    print(f"Maximum words: {max(word_counts)}")
    print(f"Average words: {sum(word_counts) / len(word_counts):.2f}")
    print(f"Chunks below 100 words: {len(small_chunks)}")
    print(f"Cross-page chunks: {len(cross_page_chunks)}")

    # Sample inspect
    print("\n--- Sample Chunk 1 ---")
    print(f"Pages: {chunks[0]['pages']}")
    print(f"Words: {chunks[0]['word_count']}")
    print(f"Text:\n{chunks[0]['text'][:300]}...")