from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

try:
    from ..qdrant_provider import get_shared_embedding_model
except (ImportError, ValueError):
    try:
        from src.engine.rag.qdrant_provider import get_shared_embedding_model
    except (ImportError, ValueError):
        get_shared_embedding_model = lambda model="Qwen/Qwen3-Embedding-0.6B", device="cuda": SentenceTransformer(model, device=device)


class BetterContext:
    def __init__(self, embedding_model=None):
        self.REDUNDANCY_THRESHOLD = 0.75
        self.embedding_model = (
            embedding_model
            if embedding_model is not None
            else get_shared_embedding_model("Qwen/Qwen3-Embedding-0.6B", device="cuda")
        )

    def better_context(self, *args, **kwargs) -> tuple[str, list]:
        """Extract chunks from reranker output with redundancy filtering."""
        if len(args) >= 2 and isinstance(args[0], str):
            reranked_results = args[1]
            max_words = args[2] if len(args) > 2 else kwargs.get("max_words", 1200)
        elif len(args) >= 1:
            reranked_results = args[0]
            max_words = args[1] if len(args) > 1 else kwargs.get("max_words", 1200)
        else:
            reranked_results = kwargs.get("reranked_results", [])
            max_words = kwargs.get("max_words", 1200)

        if not reranked_results:
            return "", []

        # Step 1 — Extract chunk texts
        chunk_texts = [
            chunk["text"]
            for (chunk, _), _ in reranked_results
        ]

        # Step 2 — Generate normalized embeddings
        embeddings = self.embedding_model.encode(
            chunk_texts,
            normalize_embeddings=True
        )

        # Step 3 — Track embeddings of chunks we keep
        kept_embeddings = []
        kept_chunks = []

        # Step 4–6 — Check each chunk for redundancy
        for index, embedding in enumerate(embeddings):

            chunk = reranked_results[index][0][0]

            is_redundant = False

            if kept_embeddings:
                similarities = np.dot(
                    np.array(kept_embeddings),
                    embedding
                )

                print(
                    f"Chunk {chunk['id']} similarities: "
                    f"{similarities}"
                )

                if np.max(similarities) >= self.REDUNDANCY_THRESHOLD:
                    is_redundant = True

            # Step 5 — Keep non-redundant chunk
            if not is_redundant:
                kept_chunks.append(chunk)
                kept_embeddings.append(embedding)

        # Step 7 — Build final context with word budget
        context = []
        word_count = 0
        final_chunks=[]

        for chunk in kept_chunks:
            chunk_text = chunk["text"]
            chunk_words = len(chunk_text.split())

            if word_count + chunk_words > max_words:
                break

            context.append(chunk_text)
            final_chunks.append(chunk) 
            word_count += chunk_words
        # Step 8 — Return final context and final chunks
        return "\n\n".join(context), final_chunks    
        # print("\n===== REDUNDANCY VERIFICATION =====")
        # print(f"Before filtering: {len(reranked_results)}")
        # print(f"After filtering: {len(kept_chunks)}")

        # print("Kept chunks:")
        # for chunk in kept_chunks:
        #     print(f"Chunk {chunk['id']} | Pages {chunk['pages']}")

        # # Step 8 — Return final context
        # return "\n\n".join(context), kept_chunks

    def build_structured_context(self, kept_chunks):
        if not kept_chunks:
            return [], {}

        context = []
        source_map = {}

        for source_id, chunk in enumerate(kept_chunks, 1):
            raw_source = chunk.get("source" , "")
            file_name = Path(raw_source).name if raw_source else "Document"

            pages = chunk.get("pages",[])
            page_info = f"PAGE: {', '.join(map(str, pages))}" if pages else "PAGE: N/A"
            header = f"--- [Source {source_id}] DOCUMENT: {file_name} | {page_info} ---"
            
            context_entry = {
                "source_id": source_id,
                "file": raw_source,
                "filename": file_name,
                "pages": pages,
                "header": header,
                "text": chunk["text"],
            }

            context.append(context_entry)

            source_map[source_id] = {
                "chunk_id": chunk.get("id"),
                "file": raw_source,
                "pages": pages,
            }

        return context, source_map