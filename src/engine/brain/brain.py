from __future__ import annotations

import json

import ollama

try:
    from engine.brain.knowledge_router import KnowledgeRouter
    from engine.brain.query_condenser import QueryCondenser
    from engine.rag.rag_manager import RAGManager
except (ImportError, ValueError):
    # pyrefly: ignore [missing-import]
    from src.engine.brain.knowledge_router import KnowledgeRouter

    # pyrefly: ignore [missing-import]
    from src.engine.brain.query_condenser import QueryCondenser

    # pyrefly: ignore [missing-import]
    from src.engine.rag.rag_manager import RAGManager


class Brain: #created a blueprint or template for out brain of AI 
    def __init__(self):
        self._conversation = []
        self._rag_manager = RAGManager()
        self._router = KnowledgeRouter()
        self._condenser = QueryCondenser()
        self.last_sources: str | None = None
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
    def respond(self, message: str) -> tuple[str, str | None]: #message is string inside method respond
        self._conversation.append({
            "role" : "user",
            "content" : message
        })

        indexed_docs = self._rag_manager.list_indexed_documents()
        route = self._router.classify(
            query=message,
            indexed_documents=indexed_docs,
            conversation_history=self._conversation
        )

        # 1. DOCUMENT_RETRIEVAL or HYBRID -> Route to RAG knowledge base
        if route in ("DOCUMENT_RETRIEVAL", "HYBRID"):
            try:
                # Reformulate ambiguous follow-ups into standalone queries
                retrieval_query = self._condenser.condense(
                    conversation_history=self._conversation[:-1],
                    follow_up_query=message,
                )
                answer, sources = self._rag_manager.ask(retrieval_query)
                self.last_sources = sources
                ai_respond = str(answer or "")
                self._conversation.append({
                    "role" : "assistant",
                    "content" : ai_respond
                })
                return ai_respond, sources
            except Exception:  # noqa: BLE001, S110
                # If retrieval fails unexpectedly, gracefully fall back to general chat
                pass

        # 2. CONVERSATIONAL -> Direct LLM chat
        self.last_sources = None
        messages = [
            {"role": "system", "content": self._system_prompt},
            *self._conversation
        ]
        try:
            response = ollama.chat(
                model="qwen2.5-coder:7b",
                messages=messages,
            )
            raw_content = (
                response.message.content
                if hasattr(response, "message")
                else response["message"]["content"]
            )
            ai_respond = str(raw_content or "")
            self._conversation.append({
                "role" : "assistant",
                "content" : ai_respond
            })
            return ai_respond, None
        except Exception as e:
            if self._conversation and self._conversation[-1]["role"] == "user":
                self._conversation.pop()
            return f"Error , Something went wrong : {e}", None



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
        system_prompt = r"""You are Thanatos an intent classifier for a desktop AI assistant.
Analyze the user's message and determine what they want to do.

Return a JSON object with EXACTLY these fields:
{
    "action": "<action>",
    "target": "<target_or_null>",
    "folder": "<folder_or_null>"
}

Allowed actions:
- "analyze_screen": When the user asks what is visible on the screen,
  asks about an error, code, application, game, text, or anything
  that requires looking at the current screen.
  Set "target" to null and "folder" to null.
- "look_at_screen": When user asks to look at the screen, capture the screen, take a screenshot, or analyze the current screen content. Set "target": null and "folder": null.
- "take_screenshot": When the user asks to take, capture, or screenshot the screen. Set "target": null and "folder": null.
- "open_application": When user asks to open, launch, or run an app (e.g. "open spotify", "launch blender", "start chrome"). Set "target" to the app name. "folder": null.
- "close_application": When user asks to close, exit, or quit an app (e.g. "close chrome", "quit spotify"). Set "target" to the app name. "folder": null.
- "open_file": When user asks to open a specific file or folder (e.g. "open my resume pdf in Downloads", "open the photo on Desktop"). Set "target" to the file name, and "folder" to the folder name if mentioned (or null).
- "delete_file": When user asks to delete or remove a file (e.g. "delete test.txt", "remove old_resume.pdf"). Set "target" to the file name, and "folder" to the folder name if mentioned (or null).
- "delete_folder": When user asks to delete or remove a folder/directory. Set "target" to folder name.
- "shutdown": When user asks to turn off or shut down the PC. "target": null, "folder": null.
- "restart": When user asks to restart or reboot the PC. "target": null, "folder": null.
- "play_music": When user asks to play a song, music, track, or artist on Spotify (e.g. "play Starboy", "play music by The Weeknd", "play Bohemian Rhapsody on Spotify"). Set "target" to the song or artist name. "folder": null.
- "index_document": When the user asks to index, add, or ingest a document into Thanatos's knowledge base (e.g. "index D:\Documents\ml.pdf"). Set "target" to the full file path and "folder" to null.
- "ask_document": When the user asks a question about the indexed document or knowledge base (e.g. "what does the document say about AI?", "ask document what is machine learning", "search document for transformers"). Set "target" to the user's question and "folder" to null.
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
            raw_content = (
                response.message.content
                if hasattr(response, "message")
                else response["message"]["content"]
            )
            content = str(raw_content or "{}")
            result = json.loads(content)
            if isinstance(result, dict):
                return result
            return {"action": "chat", "target": None, "folder": None}
        except Exception:
            return {"action": "chat", "target": None, "folder": None}

    
    def index_document(self, filepath: str) -> str:
        try:
            self._rag_manager.index_document(filepath)
            return f"Document indexed successfully: {filepath}"
        except Exception as e:
            return f"Error indexing document: {e}"
            
    def ask_document(self, question: str) -> tuple[str, str]:
        try:
            answer, sources = self._rag_manager.ask(question)
            return str(answer), str(sources)
        except Exception as e:
            return f"Error asking document: {e}", ""
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