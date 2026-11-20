import pymupdf
from sentence_transformers import SentenceTransformer, util

PDF_PATH = "benchmark_data/aiml.pdf"

MODEL_NAME = "Qwen/Qwen3-Embedding-0.6B"


# ---------------------------------------------------------
# 1. LOAD EMBEDDING MODEL
# ---------------------------------------------------------

print("Loading embedding model...")

model = SentenceTransformer(
    MODEL_NAME,
    device="cuda"
)

print("Model loaded.")
print("Device:", model.device)
print("Embedding dimensions:", model.get_embedding_dimension())


# ---------------------------------------------------------
# 2. EXTRACT PDF
# ---------------------------------------------------------

def extract_pages(pdf_path):

    document = pymupdf.open(pdf_path)

    pages = []

    for page_number, page in enumerate(document, start=1):

        text = page.get_text("text").strip()

        if text:
            pages.append({
                "page": page_number,
                "text": text
            })

    document.close()

    return pages


# ---------------------------------------------------------
# 3. CHUNK TEXT
# ---------------------------------------------------------

def chunk_text(text, words_per_chunk=180):

    words = text.split()

    chunks = []

    for i in range(0, len(words), words_per_chunk):

        chunk = " ".join(
            words[i:i + words_per_chunk]
        )

        if chunk.strip():
            chunks.append(chunk)

    return chunks


# ---------------------------------------------------------
# 4. BUILD CHUNKS
# ---------------------------------------------------------

print("\nExtracting document...")

pages = extract_pages(PDF_PATH)

chunks = []

for page in pages:

    page_chunks = chunk_text(
        page["text"]
    )

    for chunk in page_chunks:

        chunks.append({
            "page": page["page"],
            "text": chunk
        })


print("Pages extracted:", len(pages))
print("Chunks created:", len(chunks))


# ---------------------------------------------------------
# 5. SHOW CHUNKS
# ---------------------------------------------------------

print("\n==============================")
print("DOCUMENT CHUNKS")
print("==============================")

for index, chunk in enumerate(chunks):

    print(
        f"\nChunk {index + 1}"
        f" | Page {chunk['page']}"
    )

    print("-" * 70)

    print(
        chunk["text"][:700]
    )


# ---------------------------------------------------------
# 6. CREATE EMBEDDINGS
# ---------------------------------------------------------

print("\n==============================")
print("CREATING EMBEDDINGS")
print("==============================")

texts = [
    chunk["text"]
    for chunk in chunks
]

chunk_embeddings = model.encode(
    texts,
    normalize_embeddings=True,
    show_progress_bar=True
)

print("Embeddings created.")
print("Shape:", chunk_embeddings.shape)


# ---------------------------------------------------------
# 7. INTERACTIVE RETRIEVAL TEST
# ---------------------------------------------------------

print("\n==============================")
print("INTERACTIVE RETRIEVAL")
print("==============================")

while True:

    question = input(
        "\nEnter a question "
        "(or type 'exit'): "
    ).strip()

    if question.lower() == "exit":
        break

    if not question:
        continue


    # Encode question
    query_embedding = model.encode(
        question,
        normalize_embeddings=True,
        prompt_name="query"
    )


    # Calculate similarity
    scores = util.cos_sim(
        query_embedding,
        chunk_embeddings
    )[0]


    # Get top 5
    top_results = scores.argsort(
        descending=True
    )[:5]


    print("\nTop 5 results:")
    print("=" * 70)


    for rank, index in enumerate(
        top_results,
        start=1
    ):

        index = index.item()

        score = scores[index].item()

        chunk = chunks[index]

        print(
            f"\n#{rank}"
        )

        print(
            f"Score: {score:.4f}"
        )

        print(
            f"Chunk: {index + 1}"
        )

        print(
            f"Page: {chunk['page']}"
        )

        print(
            "Text:"
        )

        print(
            chunk["text"][:700]
        )