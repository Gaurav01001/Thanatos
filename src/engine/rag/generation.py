import ollama


class RAGGenerator:

    def build_prompt(self, question, context, source_text):
        if isinstance(context, list):
            context_text = "\n\n".join(
                f"[Source {item['source_id']}]\n{item['text']}"
                if isinstance(item, dict) and "source_id" in item and "text" in item
                else str(item)
                for item in context
            )
        else:
            context_text = context

        prompt = f"""
You are a question-answering assistant.

Answer the user's question using only the provided context.

When making a factual claim based on the context, cite the supporting
source using [Source N] immediately after the claim.

Do not invent source numbers.
Do not cite a source unless the context supports the claim.
Only cite a source if the provided context from that source directly
supports the claim.

If multiple sources support a claim, cite all relevant sources.

Do not use a source merely because it is present in the source list.

Every citation must correspond to the source containing the evidence
for the preceding claim.

If the context does not contain enough information to answer something,
say that the information is not available in the provided context.

User Question:
{question}

Context:
{context_text}

Sources:
{source_text}

Answer:
"""
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
        except Exception as e:
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