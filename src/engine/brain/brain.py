import ollama
class Brain: #created a blueprint or template for out brain of AI 
    def __init__(self):
        self._conversation = []

    def respond(self, message: str) -> str: #message is string inside method respond
        self._conversation.append({
            "role" : "user",
            "content" : message
        })
        
        response = ollama.chat(
            model="qwen2.5-coder:7b",
            messages=self._conversation,
        )
        ai_respond = response.message.content

        self._conversation.append({
            "role" : "assistant",
            "content" : ai_respond
        })

        return ai_respond

            #      THANATOS
            #         │
            #  ┌──────┴──────┐
            #  │   Runtime   │
            #  └──────┬──────┘
            #         │
            #   StateManager
            #         │
            #  STARTING → IDLE
            #         │
            #       Brain
            #         │
            #  Conversation
            #     Memory
            #         │
            #      Ollama
            #         │
            #  Qwen 2.5 Coder
            #         │
            #      Response