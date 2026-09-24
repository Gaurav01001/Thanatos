from __future__ import annotations

import json
from typing import ClassVar

import ollama


class KnowledgeRouter:
    """Classifies user queries into CONVERSATIONAL, DOCUMENT_RETRIEVAL, or HYBRID."""

    DOCUMENT_KEYWORDS: ClassVar[set[str]] = {
        "the document", "the pdf", "the file", "the paper",
        "in the notes", "indexed document", "according to the doc",
        "what does the pdf say", "in chapter", "page number"
    }

    HYBRID_INDICATORS: ClassVar[set[str]] = {
        "compare", "difference between", "versus", "vs",
        "how does it improve", "better than", "and who wrote",
        "explain", "critique", "and what"
    }

    def __init__(self, model: str = "qwen2.5-coder:7b"):
        self.model = model

    def classify(
        self,
        query: str,
        indexed_documents: list[str] | None = None,
        conversation_history: list | None = None
    ) -> str:
        """
        Determines the knowledge path for the given query.
        Returns: 'CONVERSATIONAL' | 'DOCUMENT_RETRIEVAL' | 'HYBRID'
        """
        clean_query = query.strip().lower()

        # Fast-Path 1: If no documents are indexed, default to CONVERSATIONAL
        if indexed_documents is not None and len(indexed_documents) == 0:
            return "CONVERSATIONAL"

        # Fast-Path 2: Check for explicit document keywords
        has_doc_keyword = any(kw in clean_query for kw in self.DOCUMENT_KEYWORDS)
        
        # Check if the user mentioned a specific indexed document name (e.g. "aiml.pdf")
        if indexed_documents:
            for doc in indexed_documents:
                doc_name = doc.split("\\")[-1].split("/")[-1].lower()
                if doc_name in clean_query:
                    has_doc_keyword = True
                    break

        if has_doc_keyword:
            # If it has document keywords AND hybrid comparison indicators:
            if any(ind in clean_query for ind in self.HYBRID_INDICATORS):
                return "HYBRID"
            return "DOCUMENT_RETRIEVAL"

        # Fast-Path 3: Greetings & short chit-chat
        if clean_query in {"hi", "hello", "hey", "status", "who are you", "what can you do"}:
            return "CONVERSATIONAL"

        # LLM Classification for ambiguous queries
        return self._classify_with_llm(query, indexed_documents)

    def _classify_with_llm(self, query: str, indexed_documents: list[str] | None = None) -> str:
        doc_context = ""
        if indexed_documents:
            doc_context = f"Indexed document filenames: {', '.join(indexed_documents)}"

        system_prompt = f"""You are a query classifier for an AI assistant.
Determine whether answering the user query requires consulting indexed documents.

{doc_context}

Categories:
1. "CONVERSATIONAL": General chit-chat, programming help, general knowledge, math, definitions not tied to a specific file.
2. "DOCUMENT_RETRIEVAL": Asking for specific information, data, summaries, or facts from user's indexed documents.
3. "HYBRID": Needs both general conceptual reasoning/theory AND specific document facts or comparison.

Return ONLY a JSON object: {{"route": "CONVERSATIONAL" | "DOCUMENT_RETRIEVAL" | "HYBRID"}}"""

        try:
            response = ollama.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": query}
                ],
                format="json",
                options={"temperature": 0.0}
            )

            raw = (
                response.message.content
                if hasattr(response, "message")
                else response["message"]["content"]
            )
            result = json.loads(raw or "{}")
            route = result.get("route", "").upper()

            if route in ("CONVERSATIONAL", "DOCUMENT_RETRIEVAL", "HYBRID"):
                return route
            return "CONVERSATIONAL"
        except Exception:  # noqa: BLE001
            return "CONVERSATIONAL"

if __name__ == "__main__":
    router = KnowledgeRouter()
    docs = ["aiml.pdf"]

    test_queries = [
        ("Hello, who are you?", "CONVERSATIONAL"),
        ("Write a python function to reverse a string", "CONVERSATIONAL"),
        ("What does aiml.pdf say about transformers?", "DOCUMENT_RETRIEVAL"),
        ("Summarize chapter 2 of the document", "DOCUMENT_RETRIEVAL"),
        ("What is machine learning and what does the PDF say about it?", "HYBRID"),
        ("Compare backpropagation with the author's method in the PDF", "HYBRID"),
    ]

    print("--- TESTING KNOWLEDGE ROUTER ---")
    for q, expected in test_queries:
        decision = router.classify(q, indexed_documents=docs)
        status = "PASS" if decision == expected else f"FAIL (got {decision})"
        print(f"[{status}] Query: '{q}' -> {decision}")
