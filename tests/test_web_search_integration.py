from __future__ import annotations

import sys
from pathlib import Path

# Add project root and src to sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))
sys.path.insert(0, str(root_dir / "src"))

from engine.brain.brain import Brain
from engine.core.response import Response
from engine.web.search import WebSearchEngine


def test_web_search_unit():
    print("--- [TEST 1] Testing WebSearchEngine Unit & Location Injection ---")
    engine = WebSearchEngine()
    results = engine.search("best dosa near me", max_results=3)
    print(f"Location configured: {engine.location}")
    print(f"Results fetched: {len(results)}")
    assert len(results) > 0, "Expected at least 1 search result"

    context_block, sources = engine.format_context(results)
    assert "[Web Result 1]:" in context_block
    assert "[Web 1:" in sources
    print("[PASS] WebSearchEngine successfully retrieved live cards and formatted citations.\n")


def test_brain_web_routing_and_synthesis():
    print("--- [TEST 2] Testing Brain.respond() Web Search Routing & Dual-Track Output ---")
    brain = Brain()
    query = "What is the latest stable version of PyTorch?"
    print(f"Query: '{query}'")

    response = brain.respond(query)
    assert isinstance(response, Response), f"Expected Response object, got {type(response)}"
    print(f"Route: {response.metadata.get('route')}")
    assert response.metadata.get("route") == "WEB_SEARCH", f"Expected WEB_SEARCH route, got: {response.metadata}"

    print(f"Display text:\n{response.display_text}\n")
    print(f"Sources:\n{response.sources}\n")
    print(f"Spoken text:\n{response.speech_text}\n")

    assert response.display_text and len(response.display_text) > 0
    assert response.sources is not None and "[Web" in response.sources
    assert response.speech_text and len(response.speech_text) > 0
    print("[PASS] Brain routed live question to WEB_SEARCH, synthesized answer, and populated web sources.\n")


def test_conversational_non_web_regression():
    print("--- [TEST 3] Testing Brain Conversational Non-Web Regression ---")
    brain = Brain()
    query = "Say hello in one word."
    print(f"Query: '{query}'")

    response = brain.respond(query)
    assert response.metadata.get("route") == "CONVERSATIONAL", f"Expected CONVERSATIONAL route, got {response.metadata}"
    assert response.sources is None, f"Expected no sources for greeting, got: {response.sources}"
    print(f"Brain: {response.display_text}")
    print("[PASS] Brain correctly leaves greetings in CONVERSATIONAL without triggering web search.\n")


if __name__ == "__main__":
    print("==================================================")
    print("STAGE 3: HEADLESS WEB SEARCH INTEGRATION TESTS")
    print("==================================================\n")
    test_web_search_unit()
    test_brain_web_routing_and_synthesis()
    test_conversational_non_web_regression()
    print("==================================================")
    print("ALL STAGE 3 WEB SEARCH INTEGRATION TESTS PASSED!")
    print("==================================================")
