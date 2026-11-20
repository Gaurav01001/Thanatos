from __future__ import annotations

import json
import logging
import re

import ollama

logger = logging.getLogger(__name__)
try:
    from engine.brain.knowledge_router import KnowledgeRouter
    from engine.brain.query_condenser import QueryCondenser
    from engine.clipboard.smart_fix import (
        SmartFixResult,
        build_smart_fix_system_prompt,
        detect_content_type,
        parse_smart_fix_response,
    )
    from engine.core.ollama_service import ensure_ollama_running, safe_ollama_call
    from engine.core.response import Response
    from engine.memory.user_memory import UserMemory
    from engine.rag.rag_manager import RAGManager
    from engine.web.search import WebSearchEngine
except (ImportError, ValueError):
    # pyrefly: ignore [missing-import]
    from src.engine.brain.knowledge_router import KnowledgeRouter

    # pyrefly: ignore [missing-import]
    from src.engine.brain.query_condenser import QueryCondenser

    # pyrefly: ignore [missing-import]
    from src.engine.clipboard.smart_fix import (
        SmartFixResult,
        build_smart_fix_system_prompt,
        detect_content_type,
        parse_smart_fix_response,
    )

    # pyrefly: ignore [missing-import]
    from src.engine.core.ollama_service import ensure_ollama_running, safe_ollama_call

    # pyrefly: ignore [missing-import]
    from src.engine.core.response import Response

    # pyrefly: ignore [missing-import]
    from src.engine.memory.user_memory import UserMemory

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
        try:
            self._user_memory = UserMemory()
        except Exception as e:  # noqa: BLE001
            logger.warning("Failed to initialize UserMemory in Brain: %s", e)
            self._user_memory = None
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
                    user_context = self._user_memory.build_context_prompt() if self._user_memory else ""
                    web_system_prompt = f"""You are Thanatos, an intelligent, perceptive desktop personal AI assistant.
Answer the user's question directly, accurately, and conversationally using the live web search findings below.

Guidelines:
1. Direct Recommendations & Specifics: If the user is asking for product suggestions, recommendations, or buying advice (e.g. perfumes, tech, clothes, places):
   - Suggest 2 to 3 specific items that match their constraints (budget, season, preferences).
   - State the approximate real-world price (e.g. ₹X,XXX or $XX) and why it fits (scent notes, specs, pros/cons).
   - Name a clear top pick or best overall value.
2. Fact & Information Queries: If the user is asking about current events, sports, weather, or release dates, state the direct facts immediately.
3. Conversational Tone: Speak naturally like an expert friend (e.g. "You could go for...", "A great pick is...").
4. Zero "Go Search Yourself": NEVER tell the user to go visit a website or search Google/Amazon themselves—synthesize and deliver the actual recommendation directly.
5. Formatting: Use clean markdown bullet points for readability.

User Location / Locale: {self._web_search.location}

Live Web Search Findings:
{context_block}"""
                    if user_context:
                        web_system_prompt = f"{web_system_prompt}\n\n{user_context}"
                    web_messages = [
                        {"role": "system", "content": web_system_prompt},
                        *self._conversation,
                    ]
                    response = safe_ollama_call(
                        ollama.chat,
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
        user_context = self._user_memory.build_context_prompt() if self._user_memory else ""
        system_content = self._system_prompt
        if user_context:
            system_content = f"{self._system_prompt}\n\n{user_context}"

        messages = [
            {"role": "system", "content": system_content},
            *self._conversation
        ]
        try:
            response = safe_ollama_call(
                ollama.chat,
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
            err_str = str(e)
            if "failed to connect" in err_str.lower() or "connection" in err_str.lower():
                err_msg = "Error: Failed to connect to Ollama. Thanatos attempted to start Ollama automatically, but could not connect. Please check that Ollama is installed and running."
            else:
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

        # 0ms Fast-Path 1.5: Algorithmic DSA Mentor queries
        hint_phrases = (
            "give me a hint", "hint on this", "algorithmic hint", "need a hint",
            "give a hint", "hint for this problem", "nudge me", "give me an intuition",
            "leetcode hint", "help me with this problem", "help me solve this problem"
        )
        debug_phrases = (
            "why does this test fail", "why is this test case failing", "why does test fail",
            "debug my code", "debug this test", "find the bug", "why did this fail"
        )
        complexity_phrases = (
            "what is the time complexity", "what's the time complexity",
            "what is the space complexity", "what's the complexity", "complexity of my code"
        )
        solution_phrases = (
            "show me the optimal solution", "give me the full solution",
            "show the optimal code", "show me the solution"
        )

        if any(p in clean for p in hint_phrases):
            return {"action": "dsa_mentor", "target": message, "folder": "hint"}
        if any(p in clean for p in debug_phrases):
            return {"action": "dsa_mentor", "target": message, "folder": "debug"}
        if any(p in clean for p in complexity_phrases):
            return {"action": "dsa_mentor", "target": message, "folder": "complexity"}
        if any(p in clean for p in solution_phrases):
            return {"action": "dsa_mentor", "target": message, "folder": "solution"}

        # 0ms Fast-Path 1.8: Browser Automation Primitives (Stage 7)
        browse_url_match = re.match(
            r"^(?:can you\s+|could you\s+|please\s+)?(?:browse to|browse|visit|go to|open website|open url|navigate to)\s+(https?://\S+|[a-zA-Z0-9_\-]+\.[a-zA-Z]{2,}(?:/\S*)?)$",
            clean,
        )
        if browse_url_match:
            target = browse_url_match.group(1).strip()
            return {"action": "browse_url", "target": target, "folder": None}

        browser_search_match = re.match(
            r"^(?:can you\s+|could you\s+|please\s+)?(?:search on browser for|browser search for|browser search|search in browser for|search web on browser for|open browser and search for)\s+(.+)$",
            clean,
        )
        if browser_search_match:
            target = browser_search_match.group(1).strip()
            return {"action": "browse_web", "target": target, "folder": None}

        # 0ms Fast-Path 1.9: Persistent User Memory (Stage 8)
        # 1. Wipe all memory (Requires confirmation)
        if clean in (
            "clear all memories", "clear my memory", "wipe my memory", "wipe memory",
            "forget everything about me", "erase all memories", "delete all memories",
            "clear all memory", "wipe all memory", "reset all memory"
        ):
            return {"action": "wipe_memory", "target": None, "folder": None}

        # 2. Specific Name / Identity Recall
        if clean in (
            "what is my name", "what's my name", "do you know my name", "who am i",
            "tell me my name", "do you know who i am", "what is my identity"
        ):
            return {"action": "recall_memory", "target": "name", "folder": "query"}

        # 3. General Memory Recall
        if clean in (
            "what do you know about me", "what do you remember about me", "show my memories",
            "show saved memories", "list my memories", "what are my preferences",
            "show my preferences", "what do you remember", "show memory", "my saved info"
        ):
            return {"action": "recall_memory", "target": None, "folder": "all"}

        # 4. Save User Fact / Name: "my name is <name>", "call me <name>"
        name_match = re.match(
            r"^(?:hi\s+|hello\s+|hey\s+)?(?:my name is|call me)\s+([a-zA-Z0-9_\-\.\s]+?)$",
            clean,
        )
        if name_match and not any(k in clean for k in ("listening", "ready", "running", "talking", "asking", "writing")):
            target = name_match.group(1).strip()
            return {"action": "save_memory", "target": f"name: {target}", "folder": "profile"}

        # 5. Attribute Specific Recall: "what is my <attribute>", "do you remember my <attribute>"
        attr_recall_match = re.match(
            r"^(?:can you tell me\s+|do you know\s+|what is\s+|what's\s+|do you remember\s+|tell me\s+)my\s+([a-zA-Z0-9_\-\s]+?)$",
            clean,
        )
        if attr_recall_match and not any(k in clean for k in ("screen", "code", "file", "folder", "app")):
            target = attr_recall_match.group(1).strip()
            return {"action": "recall_memory", "target": target, "folder": "query"}

        # 6. Delete specific memory: "forget my <attribute>", "delete memory about <attribute>"
        forget_match = re.match(
            r"^(?:please\s+|can you\s+)?(?:forget|delete memory(?: about)?)\s+(?:my\s+)?([a-zA-Z0-9_\-\s]+?)$",
            clean,
        )
        if forget_match:
            target = forget_match.group(1).strip()
            return {"action": "delete_memory", "target": target, "folder": "key"}

        # 7. Explicit Remember Directive: "remember that <fact>", "remember <fact>"
        remember_match = re.match(
            r"^(?:can you\s+|could you\s+|please\s+)?(?:remember that|remember|save memory(?: that)?|keep in mind that)\s+(.+)$",
            clean,
        )
        if remember_match:
            target = remember_match.group(1).strip()
            return {"action": "save_memory", "target": target, "folder": "note"}

        # 8. Preference Stating: "my favorite <item> is <val>", "my preferred <item> is <val>"
        pref_match = re.match(
            r"^(?:my favorite|my preferred)\s+([a-zA-Z0-9_\-\s]+?)\s+is\s+(.+)$",
            clean,
        )
        if pref_match:
            item = pref_match.group(1).strip()
            val = pref_match.group(2).strip()
            return {"action": "save_memory", "target": f"{item}: {val}", "folder": "profile"}

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

        # 0ms Fast-Path 6: Desktop Typing & Safe Writing Automation
        write_match = re.match(
            r"^(?:can you\s+|could you\s+|please\s+)?(?:type|write|draft|compose)\s+(?:an?\s+)?(.+)$",
            clean,
        )
        if write_match:
            target = write_match.group(1).strip()
            return {"action": "write_text", "target": target, "folder": None}

        paste_match = re.match(
            r"^(?:can you\s+|could you\s+|please\s+)?paste\s+(?:text\s+|this:\s*|this\s+)?(.+)$",
            clean,
        )
        if paste_match:
            target = paste_match.group(1).strip()
            return {"action": "paste_text", "target": target, "folder": None}

        # 0ms Fast-Path 7: Clipboard Intelligence & Smart Fix (Stage 10)
        clipboard_match = re.match(
            r"^(?:can you\s+|could you\s+|please\s+)?(?:smart\s*fix|fix\s+clipboard|fix\s+my\s+clipboard|polish\s+clipboard|check\s+clipboard|analyze\s+clipboard)(?:\s+(.+))?$",
            clean,
        )
        if clipboard_match or clean in ("smart fix", "fix clipboard", "fix my clipboard", "polish clipboard", "smartfix"):
            target = clipboard_match.group(1).strip() if (clipboard_match and clipboard_match.group(1)) else None
            return {"action": "smart_fix_clipboard", "target": target, "folder": None}

        # 0ms Fast-Path 8: Conversational questions / chit-chat
        chat_starts = (
            "hi", "hello", "hey", "who", "what", "where", "when", "why", "how",
            "can you", "could you", "tell me", "explain", "generate",
            "show me", "give me", "is it", "are you", "do you", "help", "good morning",
            "good evening", "good afternoon"
        )
        if any(clean.startswith(cs) for cs in chat_starts) and not any(
            k in clean for k in (
                "open ", "launch ", "start ", "close ", "quit ", "delete ",
                "shutdown", "restart", "type ", "write ", "draft ", "compose ", "paste "
            )
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
- "write_text": When user asks to type, write, compose, or draft text, letters, notes, or emails into their active window (e.g. "write an email asking for an extension", "type hello world", "draft a reply to John", "compose a formal apology"). Set "target" to the drafting instructions/topic. "folder": null.
- "paste_text": When user asks to paste text into the active window (e.g. "paste hello world", "paste this"). Set "target" to the text to paste. "folder": null.
- "send_email": When user asks to send or dispatch an email. Set "target" to recipient or topic. "folder": null.
- "send_message": When user asks to send or post a message. Set "target" to recipient or topic. "folder": null.
- "dsa_mentor": When user asks for a hint, debugging help, time complexity, or algorithmic guidance on code or a problem visible on their screen (e.g. "give me a hint", "why does test 3 fail", "check my code", "what's the time complexity"). Set "target" to the user query and "folder" to mode ("hint", "debug", "complexity", or "solution").
- "browse_url": When the user asks to visit, navigate to, or browse a specific web URL or website (e.g. "visit github.com", "browse https://news.ycombinator.com", "go to wikipedia.org", "open website arxiv.org"). Set "target" to the URL or domain. "folder": null.
- "browse_web": ONLY when the user explicitly asks to open, control, or use their web browser to search or view web pages (e.g. "open browser and search for laptops", "search on browser for Python docs", "in chrome search for ..."). DO NOT use this for normal questions, product suggestions, recommendations, prices, or advice (use "chat" instead). Set "target" to the query. "folder": null.
- "save_memory": When the user tells you personal facts, preferences, their name, or asks you to remember something (e.g. "my name is Gaurav", "remember that I code in Python", "remember that I prefer dark mode"). Set "target" to the fact or preference. "folder": "profile" or "note".
- "recall_memory": When the user asks what you know/remember about them, or asks for their name/preferences (e.g. "what is my name?", "who am I?", "what do you remember about me?", "show my preferences"). Set "target" to the specific attribute name (e.g. "name") or null for all memories. "folder": null.
- "delete_memory": When the user asks to forget a specific fact (e.g. "forget my name", "delete memory about project"). Set "target" to the attribute to forget. "folder": null.
- "wipe_memory": When the user asks to erase all memories or forget everything about them (e.g. "forget everything about me", "clear all saved memories"). "target": null, "folder": null.
- "smart_fix_clipboard": When the user asks to inspect, fix, debug, format, or polish whatever is copied in their clipboard (e.g. "smart fix", "fix clipboard", "fix my clipboard", "polish clipboard"). Set "target" to null and "folder" to null.
- "chat": For all conversations, greetings, questions, product suggestions, recommendations, buying advice, prices, reviews, comparisons, asking about document contents/authors/facts (e.g. "suggest a winter perfume", "what is the best phone under 20k", "who prepared notes in aiml.pdf?"), or help. "target": null, "folder": null.

Return ONLY a JSON object:"""

        try:
            response = safe_ollama_call(
                ollama.chat,
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

    def draft_text(self, prompt: str) -> str:
        """
        Synthesizes raw content (email, letter, note, or dictated text)
        to paste directly into the user's active window with zero conversational preamble.
        """
        if not prompt or not prompt.strip():
            return ""

        system_prompt = (
            "You are a desktop writing assistant. "
            "The user will give you a topic or prompt for text to be typed into their active document. "
            "Write the requested content directly.\n\n"
            "CRITICAL RULES:\n"
            "1. Output ONLY the raw content to be pasted.\n"
            "2. Do NOT output any conversational preamble or pleasantries (e.g. no 'Here is your draft:', 'Sure!').\n"
            "3. Do NOT include markdown code fences (```) unless the user specifically asked for computer code.\n"
            "4. Output clean, complete text ready to be typed."
        )

        try:
            response = safe_ollama_call(
                ollama.chat,
                model="qwen2.5-coder:7b",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt.strip()},
                ],
            )
            raw_content = (
                response.message.content
                if hasattr(response, "message")
                else response["message"]["content"]
            )
            text = str(raw_content or "").strip()
            if text.startswith('"""') and text.endswith('"""'):
                text = text[3:-3].strip()
            return text
        except Exception as e:  # noqa: BLE001
            logger.error("Failed to draft text via Ollama: %s", e)
            return prompt.strip()

    @property
    def user_memory(self) -> Optional[UserMemory]:
        """Provides direct access to the persistent UserMemory subsystem."""
        return self._user_memory

    def save_user_memory(self, target: str, folder: Optional[str] = "note") -> str:
        """
        Parses and stores a user fact or note into persistent memory.
        """
        if not self._user_memory:
            return "Persistent memory subsystem is unavailable."

        clean_target = target.strip()
        if ":" in clean_target and (folder == "profile" or clean_target.lower().startswith("name:")):
            key, val = clean_target.split(":", 1)
            self._user_memory.set_fact(key.strip(), val.strip())
            return f"I've remembered that your {key.strip()} is {val.strip()}."

        self._user_memory.add_note(clean_target)
        return f"I've committed that to memory: \"{clean_target}\"."

    def recall_user_memory(self, target: Optional[str] = None) -> str:
        """
        Recalls specific facts (e.g. 'name') or returns a summary of all memories.
        """
        if not self._user_memory:
            return "Persistent memory subsystem is unavailable."

        if target and target.lower() in ("name", "who am i", "my name"):
            name = self._user_memory.get_fact("name")
            if name:
                return f"Your name is {name}."
            return "I don't have your name saved in my memory yet. You can tell me by saying 'My name is [name]'."

        if target and target.lower() not in ("all", ""):
            fact = self._user_memory.get_fact(target)
            if fact:
                return f"Your {target} is {fact}."

        memories = self._user_memory.get_all_memories()
        profile = memories["profile"]
        notes = memories["notes"]

        if not profile and not notes:
            return "My memory is currently empty. You can teach me facts about yourself, like 'My name is Gaurav' or 'Remember that I code in Python'."

        lines = ["Here is what I remember about you:"]
        if profile:
            lines.append("\nProfile:")
            for k, v in profile.items():
                lines.append(f" - {k.capitalize()}: {v}")

        if notes:
            lines.append("\nSaved Notes & Preferences:")
            for n in notes:
                lines.append(f" - {n['content']}")

        return "\n".join(lines)

    def delete_user_memory(self, target: str) -> str:
        """
        Deletes a specific fact from persistent memory.
        """
        if not self._user_memory:
            return "Persistent memory subsystem is unavailable."

        clean = target.strip().lower()
        if self._user_memory.delete_fact(clean):
            return f"I've forgotten your {clean}."
        return f"I couldn't find '{clean}' in my memory records."

    def wipe_user_memory(self) -> str:
        """
        Wipes the entire persistent memory store.
        """
        if not self._user_memory:
            return "Persistent memory subsystem is unavailable."

        self._user_memory.clear_all()
        return "All persistent memories have been completely erased."

    def fix_clipboard_content(self, text: str) -> SmartFixResult:
        """
        Stage 10: Clipboard Intelligence & Smart Fix.
        Analyzes clipboard text, detects content type, applies tailored LLM fixes/polishing,
        and returns a structured SmartFixResult.
        """
        if not text or not text.strip():
            return SmartFixResult(
                content_type="empty",
                original_text="",
                fixed_text="",
                explanation="Your clipboard is empty or does not contain text.",
                speech_text="Your clipboard is empty.",
            )

        content_type = detect_content_type(text)
        system_prompt = build_smart_fix_system_prompt(content_type)

        try:
            response = safe_ollama_call(
                ollama.chat,
                model="qwen2.5-coder:7b",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text},
                ],
            )
            raw_content = (
                response.message.content
                if hasattr(response, "message")
                else response["message"]["content"]
            )
            fixed_text, explanation, speech_text = parse_smart_fix_response(
                str(raw_content or ""), content_type
            )
            return SmartFixResult(
                content_type=content_type,
                original_text=text,
                fixed_text=fixed_text,
                explanation=explanation,
                speech_text=speech_text,
            )
        except Exception as e:
            logger.error("Failed to fix clipboard content via Ollama: %s", e)
            return SmartFixResult(
                content_type=content_type,
                original_text=text,
                fixed_text=text,
                explanation=f"Error analyzing clipboard content: {e}",
                speech_text="Sorry, something went wrong while analyzing your clipboard.",
            )
    
    def _create_spoken_summary(self, text: str) -> str:
        """
        Synthesizes a complete, natural, punchy spoken summary for voice output.
        Guarantees that statements are never cut off mid-thought or mid-sentence.
        """
        if not text:
            return ""

        clean = re.sub(r"\[(?:Source|Web)\s*\d+[^\]]*\]", "", text).strip()
        clean_no_code = re.sub(r"```[\s\S]*?```", "", clean).strip()

        # Strip markdown headers, bold, italics, backticks
        clean_no_code = re.sub(r"^#+\s*", "", clean_no_code, flags=re.MULTILINE)
        clean_no_code = re.sub(r"[*_~`]", "", clean_no_code)

        lines = []
        for line in clean_no_code.splitlines():
            line = line.strip()
            if not line or line.startswith(("---", "===")):
                continue
            # Remove leading list numbering or bullet markers: '1. ', '- ', '• '
            line = re.sub(r"^\d+\.\s*", "", line)
            line = re.sub(r"^[-•*]\s*", "", line)
            lines.append(line)

        if not lines:
            return "Here is the requested information."

        joined = " ".join(lines)
        # Convert introductory colons (e.g. "Here are the best substitutes:") into natural clauses
        intro_phrases = ("here are", "for ", "the best", "top ", "you can", "you have", "there are")
        if joined.count(":") > 0 and any(joined.lower().startswith(p) for p in intro_phrases):
            joined = re.sub(r":\s*", ", such as ", joined, count=1)

        # Split into complete sentences
        raw_sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", joined) if s.strip()]
        sentences = [s for s in raw_sentences if len(re.sub(r"[^a-zA-Z0-9]", "", s)) > 1]

        if not sentences:
            return "I have displayed the full details on your screen."

        # Take lead 1-2 complete sentences
        summary = sentences[0]
        if len(sentences) > 1 and len(summary) < 140:
            summary = f"{summary} {sentences[1]}"

        if not summary.endswith((".", "!", "?")):
            summary += "."

        if len(sentences) > 2 or len(joined) > 220:
            if not summary.endswith("on your screen."):
                summary += " I've displayed the full details on your screen."

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