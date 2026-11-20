from __future__ import annotations

import sys
from pathlib import Path

# Add project root and src to sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))
sys.path.insert(0, str(root_dir / "src"))

from engine.brain.brain import Brain
from engine.core.response import Response


def test_spoken_summary_unit():
    print("--- [TEST 1] Testing _create_spoken_summary Unit Logic ---")
    brain = Brain()

    # Short query
    short_text = "Good morning! I am ready when you are."
    spoken_short = brain._create_spoken_summary(short_text)
    print(f"Original short: {short_text}")
    print(f"Spoken short:   {spoken_short}")
    assert spoken_short == short_text, f"Expected untouched short text, got: {spoken_short}"

    # Technical text with code blocks & citations
    long_tech = (
        "Linear regression models the relationship between dependent and independent variables "
        "by fitting a linear equation. It uses gradient descent or ordinary least squares to optimize weights.\n\n"
        "[Source 1: ML_Notes.pdf (p. 4)]\n\n"
        "Here is an example:\n"
        "```python\n"
        "import numpy as np\n"
        "model = LinearRegression()\n"
        "model.fit(X, y)\n"
        "```\n"
        "Make sure to normalize your features."
    )
    spoken_tech = brain._create_spoken_summary(long_tech)
    print(f"\nOriginal tech:\n{long_tech}")
    print(f"\nSpoken tech: {spoken_tech}")
    assert "```" not in spoken_tech, "Code block should be stripped from spoken summary"
    assert len(spoken_tech) < len(long_tech), "Spoken summary should be shorter than raw text"
    assert "Linear regression" in spoken_tech, "Spoken summary should retain core subject"
    print("[PASS] _create_spoken_summary handled both conversational and technical text properly.\n")


def test_response_unpacking():
    print("--- [TEST 2] Testing Response Dataclass & Unpacking Compatibility ---")
    resp = Response(
        display_text="Display text here",
        speech_text="Speech text here",
        sources="[Source 1: doc.pdf]",
    )

    # Object access
    assert resp.display_text == "Display text here"
    assert resp.speech_text == "Speech text here"
    assert resp.sources == "[Source 1: doc.pdf]"

    # Legacy tuple unpacking
    ans, src = resp
    assert ans == "Display text here"
    assert src == "[Source 1: doc.pdf]"
    print("[PASS] Response object supports both new attributes and legacy tuple unpacking.\n")


def test_brain_respond_type():
    print("--- [TEST 3] Testing Brain.respond() Return Contract ---")
    brain = Brain()
    # Test conversational query
    res = brain.respond("Say hello in one word.")
    assert isinstance(res, Response), f"Expected Response instance, got {type(res)}"
    assert res.display_text and len(res.display_text) > 0
    assert res.speech_text and len(res.speech_text) > 0
    print(f"Display text: {res.display_text}")
    print(f"Speech text:  {res.speech_text}")
    print("[PASS] Brain.respond() successfully returns Response object.\n")


if __name__ == "__main__":
    test_spoken_summary_unit()
    test_response_unpacking()
    test_brain_respond_type()
    print("==============================================")
    print("ALL STAGE 2 STEP 1 & 2 VERIFICATION TESTS PASSED!")
    print("==============================================")
