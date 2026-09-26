import ollama


class RAGGenerator:

    def build_prompt(self, question, context, source_text):
        if isinstance(context, list):
            formatted_items = []
            for item in context:
                if isinstance(item, dict) and "text" in item:
                    header = item.get("header") or f"[Source {item.get('source_id', '')}]"
                    formatted_items.append(f"{header}\n{item['text']}")
                else:
                    formatted_items.append(str(item))
            context_text = "\n\n".join(formatted_items)
        else:
            context_text = context


        prompt = f"""You are Thanatos, a knowledgeable, direct, and concise AI assistant.

Synthesize your answer to the user's question following these rules:

1. DOCUMENT FACTS & GROUNDING:
   - Use the provided context to answer questions about indexed documents, files, data, and citations.
   - Immediately cite the supporting source using [Source N] right after any factual claim derived from the context.
   - Do not invent source numbers or cite a source unless the context directly supports that specific claim.

2. GENERAL KNOWLEDGE & HYBRID REASONING:
   - If the user asks a question combining document facts with general concepts, theory, code, or opinions, use your broader general knowledge to explain the general concepts.
   - Do NOT attach [Source N] citations to general knowledge claims.

3. MISSING INFORMATION:
   - If a document-specific question cannot be answered from the context, state clearly that the document does not mention it, but provide general knowledge if relevant.

Context:
{context_text}

Sources:
{source_text}

User Question: {question}

Answer:"""
        return prompt


    def generate(self, prompt):
        try:
            response = ollama.chat(
                model="qwen2.5-coder:7b",
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )
            return response["message"]["content"]
        except Exception as e:  # noqa: BLE001
            return f"[Ollama Error: {e}. Please ensure Ollama is running and 'qwen2.5-coder:7b' is pulled.]"



if __name__ == "__main__":
    generator = RAGGenerator()

    question = "What is artificial intelligence?"

    context = """
Artificial intelligence is the field of creating systems that can
perform tasks that normally require human intelligence.
"""

    source_text = """
[Source 1]
File: benchmark_data/aiml.pdf
Pages: [2, 3]
"""

    prompt = generator.build_prompt(
        question,
        context,
        source_text
    )

    answer = generator.generate(prompt)

    print("===== GENERATED ANSWER =====")
    print(answer)