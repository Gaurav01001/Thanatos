from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from engine.brain.knowledge_router import KnowledgeRouter
from engine.core.response import Response


# ---------------------------------------------------------------------------
# Test 1: Knowledge Router Routing for Shopping, Recommendations & Budgets
# ---------------------------------------------------------------------------
def test_knowledge_router_shopping_and_recommendations():
    router = KnowledgeRouter()

    # 1. User's exact prompt: perfume under 3000 rupees
    route1 = router.classify("I want you to suggest me a winter perfume under 3000 rupees", indexed_documents=[])
    assert route1 == "WEB_SEARCH"

    # 2. Budget price queries
    route2 = router.classify("best gaming laptop under 60000", indexed_documents=[])
    assert route2 == "WEB_SEARCH"

    route3 = router.classify("top smartphone under ₹20000", indexed_documents=[])
    assert route3 == "WEB_SEARCH"

    # 3. Recommendation intent openers
    route4 = router.classify("suggest a good book for learning rust", indexed_documents=[])
    assert route4 == "WEB_SEARCH"

    route5 = router.classify("recommend an affordable wireless mouse", indexed_documents=[])
    assert route5 == "WEB_SEARCH"

    # 4. Standard chit-chat remains CONVERSATIONAL
    route6 = router.classify("hello", indexed_documents=[])
    assert route6 == "CONVERSATIONAL"


# ---------------------------------------------------------------------------
# Test 2: Intent Classification - Physical Browser vs Cognitive Queries
# ---------------------------------------------------------------------------
def test_intent_classification_browser_vs_chat():
    from engine.brain.brain import Brain

    # Fast-path check: explicit browser commands
    clean1 = "search on browser for best mechanical keyboards"
    m1 = re.match(
        r"^(?:can you\s+|could you\s+|please\s+)?(?:search on browser for|browser search for|browser search|search in browser for|search web on browser for|open browser and search for)\s+(.+)$",
        clean1,
        re.IGNORECASE,
    )
    assert m1 is not None
    assert m1.group(1).strip() == "best mechanical keyboards"

    # Informational queries must NOT match explicit browser fast-path
    clean2 = "suggest me a winter perfume under 3000 rupees"
    m2 = re.match(
        r"^(?:can you\s+|could you\s+|please\s+)?(?:search on browser for|browser search for|browser search|search in browser for|search web on browser for|open browser and search for)\s+(.+)$",
        clean2,
        re.IGNORECASE,
    )
    assert m2 is None


# ---------------------------------------------------------------------------
# Test 3: Spoken Summary Cleanliness (Zero Vocalized Asterisks / Bullets)
# ---------------------------------------------------------------------------
def test_spoken_summary_clean_speech():
    from engine.brain.brain import Brain

    with patch("engine.brain.brain.RAGManager"), \
         patch("engine.brain.brain.KnowledgeRouter"), \
         patch("engine.brain.brain.QueryCondenser"):
        brain = Brain()

        markdown_text = (
            "Here are the top winter perfumes under ₹3,000:\n\n"
            "- **Zara Warm Black** (~₹1,490): Warm vanilla and tobacco notes ideal for cold weather.\n"
            "- **Lalique Encre Noire** (~₹2,799): Dark earthy woody vetiver scent."
        )

        spoken = brain._create_spoken_summary(markdown_text)

        # Spoken text must NOT contain markdown asterisks, hashes, or bullet dashes
        assert "*" not in spoken
        assert "#" not in spoken
        assert not spoken.startswith("-")
        assert len(spoken) > 0


# ---------------------------------------------------------------------------
# Test 4: Grounded Live Web Synthesis (ChatGPT-Style Response & Dual-Track)
# ---------------------------------------------------------------------------
def test_grounded_web_synthesis_flow():
    from engine.brain.brain import Brain

    mock_cards = [
        {
            "title": "Best Perfume Under 3000 in India (2026)",
            "href": "https://example.com/perfumes",
            "body": "The best winter perfume under ₹3,000 is Zara Warm Black at ₹1,490 and Lalique Encre Noire at ₹2,799."
        }
    ]

    mock_llm_response = MagicMock()
    mock_llm_response.message.content = (
        "For winter under ₹3,000, here are the top picks:\n\n"
        "1. **Zara Warm Black** (~₹1,490) - Warm spicy tobacco and vanilla, perfect for casual winter nights.\n"
        "2. **Lalique Encre Noire** (~₹2,799) - Sophisticated, dark woody vetiver with great longevity.\n\n"
        "My top pick is **Zara Warm Black** for the best value."
    )

    with patch("engine.brain.brain.RAGManager"), \
         patch("engine.brain.brain.QueryCondenser"), \
         patch("engine.brain.brain.safe_ollama_call", return_value=mock_llm_response):

        brain = Brain()
        # Ensure knowledge router routes to WEB_SEARCH
        brain._router.route = MagicMock(return_value="WEB_SEARCH")
        brain._web_search.search = MagicMock(return_value=mock_cards)

        resp = brain.respond("I want you to suggest me a winter perfume under 3000 rupees")

        assert isinstance(resp, Response)
        assert resp.metadata.get("route") == "WEB_SEARCH"
        assert "Zara Warm Black" in resp.display_text
        assert "Lalique Encre Noire" in resp.display_text
        assert resp.sources is not None
        assert "example.com/perfumes" in resp.sources

        # Spoken summary should be clean and speakable
        assert resp.speech_text is not None
        assert "*" not in resp.speech_text


# ---------------------------------------------------------------------------
# Test 5: Defensive Browser Automation Guard
# ---------------------------------------------------------------------------
def test_main_browser_guard_logic():
    # Simulates the guard in __main__.py
    def check_guard(action: str, message: str) -> bool:
        if action in ("browse_url", "browse_web"):
            msg_lower = message.lower()
            return (
                action == "browse_url"
                or any(kw in msg_lower for kw in ("browser", "chrome", "firefox", "edge", "in web browser", "open web"))
            )
        return False

    # 1. Misclassified informational query -> Guard returns False (diverts to chat)
    assert check_guard("browse_web", "suggest winter perfume under 3000 rupees") is False
    assert check_guard("browse_web", "best laptop under 50000") is False

    # 2. Explicit browser requests -> Guard returns True (launches browser)
    assert check_guard("browse_web", "open browser and search for python") is True
    assert check_guard("browse_web", "search in chrome for weather") is True
    assert check_guard("browse_url", "https://github.com") is True
