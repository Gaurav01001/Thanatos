from __future__ import annotations

import ollama


class QueryCondenser:
    def __init__(self, model: str = "qwen2.5-coder:7b"):
        self.model = model

    def condense(self, conversation_history: list[dict], follow_up_query: str) -> str:
        """
        If prior context exists, rewrites ambiguous follow-up questions into self-contained search queries.
        If no prior context exists or rewriting fails, returns follow_up_query unchanged.
        """
        # If no conversation history, query is already standalone
        if not conversation_history:
            return follow_up_query

        # Only look at the last 2 turns (User + Assistant) to keep it lightning fast
        recent_turns = conversation_history[-4:] if len(conversation_history) >= 4 else conversation_history

        # Format conversation snippet for the prompt
        formatted_history = []
        for turn in recent_turns:
            role = "user" if turn.get("role") == "user" else "assistant"
            content = turn.get("content", "").strip()

            # Truncate long assistant responses to keep prompt tiny
            if len(content) > 250:
                content = content[:250] + "...[truncated]"

            formatted_history.append(f"{role}: {content}")

        history_str = "\n".join(formatted_history)
        system_prompt = """You are a search query reformulation specialist.
Given the chat history and the user's latest follow-up question, rewrite the follow-up question into a single, standalone search query that contains all necessary subjects and document references.
Rules:
1. Resolve all pronouns (it, that, they, them, he, she, this).
2. Retain document names, authors, or key topics mentioned in the chat.
3. DO NOT answer the question.
4. DO NOT explain your reasoning.
5. Return ONLY the reformulated question on a single line."""
        user_prompt = f"""Chat History:
{history_str}

Follow-up question: {follow_up_query}
Standalone search query:"""
        try:
            response = ollama.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                options={"temperature": 0.0}
            )
            raw = (
                response.message.content
                if hasattr(response, "message")
                else response["message"]["content"]
            )
            condensed = str(raw or "").strip().strip('"').strip("'")
            # Fallback guard: if model returned an empty string or hallucinated multiline answer
            if condensed and len(condensed.split("\n")) == 1:
                return condensed
            return follow_up_query
        except Exception:  # noqa: BLE001
            return follow_up_query


if __name__ == "__main__":
    condenser = QueryCondenser()

    # Simulate Turn 1 in chat
    mock_history = [
        {"role": "user", "content": "What does aiml.pdf say about transformers?"},
        {"role": "assistant", "content": "Transformers use self-attention mechanisms to process sequential data."}
    ]

    # Test ambiguous Turn 2
    follow_up = "Who authored them?"
    result = condenser.condense(mock_history, follow_up)

    print("\n--- QUERY CONDENSER TEST ---")
    print(f"Follow-up : {follow_up}")
    print(f"Condensed : {result}")

