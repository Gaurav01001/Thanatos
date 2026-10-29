from __future__ import annotations

import json
import logging
import re

import ollama

logger = logging.getLogger(__name__)
try:
    from engine.brain.knowledge_router import KnowledgeRouter
    from engine.brain.query_condenser import QueryCondenser
    from engine.core.response import Response
    from engine.rag.rag_manager import RAGManager
    from engine.web.search import WebSearchEngine
except (ImportError, ValueError):
    # pyrefly: ignore [missing-import]
    from src.engine.brain.knowledge_router import KnowledgeRouter

    # pyrefly: ignore [missing-import]
    from src.engine.brain.query_condenser import QueryCondenser

    # pyrefly: ignore [missing-import]
    from src.engine.core.response import Response

    # pyrefly: ignore [missing-import]
    from src.engine.rag.rag_manager import RAGManager

    # pyrefly: ignore [missing-import]
    from src.engine.web.search import WebSearchEngine


class Brain: #created a blueprint or template for out brain of AI 
    def __init__(self):
        self._conversation = []
        try:
            self._rag_manager = RAGManager()
        except Exception as e:  # noqa: BLE001
            logger.warning("Failed to initialize RAGManager in Brain: %s. Running in chat-only mode.", e)
            self._rag_manager = None
        self._router = KnowledgeRouter()
        self._condenser = QueryCondenser()
        self._web_search = WebSearchEngine()
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
    def respond(self, message: str) -> Response:
        self._conversation.append({
            "role" : "user",
            "content" : message
        })

        indexed_docs = []
        if self._rag_manager and getattr(self._rag_manager, "is_healthy", True):
            try:
                indexed_docs = self._rag_manager.list_indexed_documents()
            except Exception as e:  # noqa: BLE001
                logger.warning("Error listing indexed documents: %s", e)

        route = self._router.classify(
            query=message,
            indexed_documents=indexed_docs,
            conversation_history=self._conversation[:-1]
        )

        # 1. DOCUMENT_RETRIEVAL or HYBRID -> Route to RAG knowledge base
        if route in ("DOCUMENT_RETRIEVAL", "HYBRID") and self._rag_manager:
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
                speech_text = self._create_spoken_summary(ai_respond)
                return Response(
                    display_text=ai_respond,
                    speech_text=speech_text,
                    sources=sources,
                    metadata={"route": route},
                )
            except Exception as e:  # noqa: BLE001
                logger.warning("Document retrieval failed (%s). Gracefully degrading to direct LLM chat.", e)
                # If retrieval fails unexpectedly, gracefully fall back to general chat below

        # 2. WEB_SEARCH -> Live internet search via Headless DuckDuckGo
        if route == "WEB_SEARCH":
            try:
                cards = self._web_search.search(message)
                if cards:
                    context_block, web_sources = self._web_search.format_context(cards)
                    web_system_prompt = f"""You are Thanatos, a desktop AI assistant.
Answer the user's question accurately using the live web search results below.
Be concise, direct, and structured. Include relevant details and specifics.

Live Web Results:
{context_block}"""
                    web_messages = [
                        {"role": "system", "content": web_system_prompt},
                        *self._conversation,
                    ]
                    response = ollama.chat(
                        model="qwen2.5-coder:7b",
                        messages=web_messages,
                    )
                    raw_content = (
                        response.message.content
                        if hasattr(response, "message")
                        else response["message"]["content"]
                    )
                    ai_respond = str(raw_content or "")
                    self._conversation.append({
                        "role": "assistant",
                        "content": ai_respond,
                    })
                    self.last_sources = web_sources
                    speech_text = self._create_spoken_summary(ai_respond)
                    return Response(
                        display_text=ai_respond,
                        speech_text=speech_text,
                        sources=web_sources,
                        metadata={"route": "WEB_SEARCH"},
                    )
            except Exception as e:  # noqa: BLE001
                logger.warning("Web search execution failed (%s). Gracefully degrading to direct LLM chat.", e)

        # 3. CONVERSATIONAL -> Direct LLM chat
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
            speech_text = self._create_spoken_summary(ai_respond)
            return Response(
                display_text=ai_respond,
                speech_text=speech_text,
                sources=None,
                metadata={"route": "CONVERSATIONAL"},
            )
        except Exception as e:  # noqa: BLE001
            if self._conversation and self._conversation[-1]["role"] == "user":
                self._conversation.pop()
            err_msg = f"Error , Something went wrong : {e}"
            return Response(
                display_text=err_msg,
                speech_text="Sorry, something went wrong while processing your request.",
                sources=None,
                metadata={"error": str(e)},
            )



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
        if not message:
            return {"action": "chat", "target": None, "folder": None}

        clean = message.lower().strip().rstrip("?!.")

        # 0ms Fast-Path 1: Screen queries
        screen_phrases = (
            "screenshot", "take screenshot", "capture screen", "look at screen",
            "analyze screen", "what is on my screen", "look at my screen", "view screen"
        )
        if any(p in clean for p in screen_phrases):
            return {"action": "take_screenshot", "target": None, "folder": None}

        # 0ms Fast-Path 2: Open application or document
        open_match = re.match(
            r"^(?:can you\s+|could you\s+|please\s+)?(?:open|launch|start|run)\s+(?:the\s+)?([a-zA-Z0-9_\-\.\s]+?)(?:\s+browser|\s+app|\s+application)?$",
            clean,
        )
        if open_match:
            target = open_match.group(1).strip()
            if not target.endswith((".pdf", ".txt", ".docx", ".md", ".json", ".py", ".csv", ".xlsx")):
                return {"action": "open_application", "target": target, "folder": None}
            return {"action": "open_file", "target": target, "folder": None}

        # 0ms Fast-Path 3: Close application
        close_match = re.match(
            r"^(?:can you\s+|could you\s+|please\s+)?(?:close|quit|exit|kill)\s+(?:the\s+)?([a-zA-Z0-9_\-\.\s]+?)(?:\s+browser|\s+app|\s+application)?$",
            clean,
        )
        if close_match:
            target = close_match.group(1).strip()
            return {"action": "close_application", "target": target, "folder": None}

        # 0ms Fast-Path 4: Play music / Spotify
        if clean.startswith(("play ", "can you play ", "could you play ", "please play ")):
            song = re.sub(r"^(?:can you\s+|could you\s+|please\s+)?play\s+", "", clean)
            song = re.sub(r"\s+on\s+spotify.*$", "", song).strip()
            return {"action": "play_music", "target": song, "folder": None}

        # 0ms Fast-Path 5: Index document
        index_match = re.match(r"^(?:index|add|ingest)\s+(?:document\s+|file\s+)?(.+)$", clean)
        if index_match:
            target = index_match.group(1).strip()
            return {"action": "index_document", "target": target, "folder": None}

        # 0ms Fast-Path 6: Conversational questions / chit-chat
        chat_starts = (
            "hi", "hello", "hey", "who", "what", "where", "when", "why", "how",
            "can you", "could you", "tell me", "explain", "write", "generate",
            "show me", "give me", "is it", "are you", "do you", "help", "good morning",
            "good evening", "good afternoon"
        )
        if any(clean.startswith(cs) for cs in chat_starts) and not any(
            k in clean for k in ("open ", "launch ", "start ", "close ", "quit ", "delete ", "shutdown", "restart")
        ):
            return {"action": "chat", "target": None, "folder": None}

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
- "open_file": When user explicitly asks to open, launch, or view a file or folder on disk (e.g. "open my resume pdf in Downloads", "open the photo on Desktop"). DO NOT use this for questions asking about the contents or authors of a document. Set "target" to the file name, and "folder" to the folder name if mentioned (or null).
- "delete_file": When user asks to delete or remove a file (e.g. "delete test.txt", "remove old_resume.pdf"). Set "target" to the file name, and "folder" to the folder name if mentioned (or null).
- "delete_folder": When user asks to delete or remove a folder/directory. Set "target" to folder name.
- "shutdown": When user asks to turn off or shut down the PC. "target": null, "folder": null.
- "restart": When user asks to restart or reboot the PC. "target": null, "folder": null.
- "play_music": When user asks to play a song, music, track, or artist on Spotify (e.g. "play Starboy", "play music by The Weeknd", "play Bohemian Rhapsody on Spotify"). Set "target" to the song or artist name. "folder": null.
- "index_document": When the user asks to index, add, or ingest a document into Thanatos's knowledge base (e.g. "index D:\Documents\ml.pdf"). Set "target" to the full file path and "folder" to null.
- "chat": For all conversations, greetings, general questions, asking about document contents/authors/facts (e.g. "who prepared notes in aiml.pdf?", "what does the PDF say?"), or help. "target": null, "folder": null.

Return ONLY a JSON object:"""

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
        except Exception:  # noqa: BLE001
            return {"action": "chat", "target": None, "folder": None}

    
    def index_document(self, filepath: str) -> str:
        try:
            self._rag_manager.index_document(filepath)
            return f"Document indexed successfully: {filepath}"
        except Exception as e:  # noqa: BLE001
            return f"Error indexing document: {e}"
            
    def ask_document(self, question: str) -> tuple[str, str]:
        try:
            answer, sources = self._rag_manager.ask(question)
            return str(answer), str(sources)
        except Exception as e:  # noqa: BLE001
            return f"Error asking document: {e}", ""
    
    def _create_spoken_summary(self, text: str) -> str:
        if not text:
            return ""

        clean = re.sub(r"\[Source\s*\d+[^\]]*\]", "", text).strip()
        clean_no_code = re.sub(r"```[\s\S]*?```", "", clean).strip()
        lines = [line.strip() for line in clean_no_code.splitlines() if line.strip()]
        
        filtered_lines = [
            line for line in lines 
            if not line.startswith(("#", "```", "---", "==="))
        ]
        if not filtered_lines:
            return "Here is the requested code."
        joined_text = " ".join(filtered_lines)
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", joined_text) if s.strip()]
        if not sentences:
            return joined_text

        # If it's already concise (1-2 sentences), speak it cleanly
        if len(sentences) <= 2 and len(joined_text) <= 220:
            return joined_text

        # Otherwise extract the punchy lead sentences directly
        summary = " ".join(sentences[:2])
        if len(summary) > 220:
            summary = sentences[0]
        return summary
        
        

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