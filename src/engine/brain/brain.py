import ollama
import json

class Brain: #created a blueprint or template for out brain of AI 
    def __init__(self):
        self._conversation = []
        self._system_prompt = """
You are Thanatos, a local AI assistant.

Be concise, direct, and useful.
Your personality is dry, gritty, sarcastic, and occasionally darkly humorous.
Never Express your personality in the response. Do not talk about yourself.
Don't force jokes or explain your personality.
Don't constantly agree with the user; challenge bad ideas when appropriate.
Speak naturally and conversationally, not like a corporate assistant.
Never identify yourself as Qwen.
When the user needs a serious answer, drop the humor and be serious.
"""
    def respond(self, message: str) -> str: #message is string inside method respond
        self._conversation.append({
            "role" : "user",
            "content" : message
        })
        
        messages = [
            {"role": "system", "content": self._system_prompt},
            *self._conversation
        ]
        try:
            response = ollama.chat(
                model="qwen2.5-coder:7b",
                messages=messages,
            )
            ai_respond = response.message.content
        except Exception as e:
            ai_respond = f"Error , Something went wrong : {e}"

        self._conversation.append({
            "role" : "assistant",
            "content" : ai_respond
        })

        return ai_respond

    def clear_memory(self) -> None:
        self._conversation = []
        
# "please launch notepad"
#         ↓
#       Brain
#         ↓
# {
#     "action": "open_application",
#     "target": "notepad"
# }
#         ↓
#      main.py
#         ↓
#      Executor
    def get_intent(self, message: str) -> dict:
        system_prompt = """You are an intent classifier for a desktop AI assistant.
Analyze the user's message and determine what they want to do.

Return a JSON object with EXACTLY these fields:
{
    "action": "<action>",
    "target": "<target_or_null>",
    "folder": "<folder_or_null>"
}

Allowed actions:
- "open_application": When user asks to open, launch, or run an app (e.g. "open spotify", "launch blender", "start chrome"). Set "target" to the app name. "folder": null.
- "open_file": When user asks to open a specific file or folder (e.g. "open my resume pdf in Downloads", "open the photo on Desktop"). Set "target" to the file name, and "folder" to the folder name if mentioned (or null).
- "chat": For all normal conversations, greetings, questions, or help. "target": null, "folder": null.

Return ONLY valid raw JSON."""

        try:
            response = ollama.chat(
                model="qwen2.5-coder:7b",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message}
                ],
                format="json"
            )
            return json.loads(response.message.content)
        except Exception:
            return {"action": "chat", "target": None, "folder": None}

    
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