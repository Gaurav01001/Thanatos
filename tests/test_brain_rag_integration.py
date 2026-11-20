from __future__ import annotations

import sys
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

from src.engine.brain.brain import Brain


def run_tests():
    print("==================================================")
    print("PHASE 8 - END-TO-END BRAIN & RAG INTEGRATION TESTS")
    print("==================================================\n")

    brain = Brain()

    # ----------------------------------------------------
    # TEST 1: Pure Conversational Test
    # ----------------------------------------------------
    print("--- [TEST 1] Pure Conversational Query ---")
    q1 = "Tell me a gritty, short observation about life."
    ans1, src1 = brain.respond(q1)
    print(f"User: {q1}")
    print(f"Brain: {ans1}")
    print(f"Sources: {src1}")
    assert src1 is None, f"Expected None sources for conversational query, got: {src1}"
    assert ans1 and len(ans1) > 0, "Expected non-empty response"
    print("[PASS] Pure conversational query succeeded with 0 citations.\n")

    # ----------------------------------------------------
    # TEST 2: Pure Document Query
    # ----------------------------------------------------
    print("--- [TEST 2] Pure Document Query ---")
    q2 = "Who prepared the lecture notes in aiml.pdf and what college is mentioned?"
    ans2, src2 = brain.respond(q2)
    print(f"User: {q2}")
    print(f"Brain: {ans2}")
    print(f"Sources: {src2}")
    assert src2 is not None, "Expected valid sources for document query"
    assert "aiml.pdf" in src2, f"Expected 'aiml.pdf' in sources, got: {src2}"
    assert "[Source" in src2, f"Expected '[Source' in sources, got: {src2}"
    assert "patra" in ans2.lower() or "bhubaneswar" in ans2.lower(), f"Expected author/college in answer, got: {ans2}"
    print("[PASS] Pure document query retrieved grounded content with valid citations.\n")

    # ----------------------------------------------------
    # TEST 3: Hybrid Question Test (General + Document)
    # ----------------------------------------------------
    print("--- [TEST 3] Hybrid Question Query ---")
    q3 = "What is artificial intelligence, and who prepared the notes in aiml.pdf?"
    ans3, src3 = brain.respond(q3)
    print(f"User: {q3}")
    print(f"Brain: {ans3}")
    print(f"Sources: {src3}")
    assert ans3 and len(ans3) > 0, "Expected non-empty response"
    assert src3 is not None, "Expected document citations for the document part of hybrid query"
    assert "aiml.pdf" in src3, f"Expected 'aiml.pdf' in citations, got: {src3}"
    print("[PASS] Hybrid query successfully synthesized general knowledge and document facts.\n")

    # ----------------------------------------------------
    # TEST 4: Follow-Up Resolution (Multi-Turn Memory)
    # ----------------------------------------------------
    print("--- [TEST 4] Follow-Up Pronoun Resolution ---")
    brain.clear_memory()
    # Turn 1: Specific document query
    turn1_q = "Who prepared the lecture notes in aiml.pdf?"
    t1_ans, _t1_src = brain.respond(turn1_q)
    print(f"Turn 1 User : {turn1_q}")
    print(f"Turn 1 Brain: {t1_ans}")

    # Turn 2: Ambiguous follow-up resolving pronoun "he" / "his"
    turn2_q = "What college is he from?"
    t2_ans, t2_src = brain.respond(turn2_q)
    print(f"Turn 2 User : {turn2_q}")
    print(f"Turn 2 Brain: {t2_ans}")
    print(f"Turn 2 Sources: {t2_src}")
    assert t2_ans and len(t2_ans) > 0, "Expected non-empty response"
    ans_lower = t2_ans.lower()
    assert (
        "bhubaneswar" in ans_lower
        or "engineering" in ans_lower
        or "college" in ans_lower
        or "kharagpur" in ans_lower
        or "technology" in ans_lower
    ), f"Expected college/institute in follow-up answer, got: {t2_ans}"
    assert t2_src is not None, f"Expected sources for follow-up document query, got: {t2_src}"
    print("[PASS] Follow-up query executed with context awareness.\n")

    # ----------------------------------------------------
    # TEST 5: Irrelevant Retrieval / Out-of-Domain Query
    # ----------------------------------------------------
    print("--- [TEST 5] Irrelevant / Out-of-Domain Query ---")
    q5 = "What is the capital of France and what is a good recipe for chocolate cookies?"
    ans5, src5 = brain.respond(q5)
    print(f"User: {q5}")
    print(f"Brain: {ans5}")
    print(f"Sources: {src5}")
    assert src5 is None, f"Expected None sources for out-of-domain query, got: {src5}"
    assert "paris" in ans5.lower(), f"Expected 'Paris' in answer, got: {ans5}"
    print("[PASS] Out-of-domain query answered without false document citations.\n")

    print("==================================================")
    print("ALL 5 SYSTEM INTEGRATION TESTS PASSED SUCCESSFULLY")
    print("==================================================")


if __name__ == "__main__":
    run_tests()
