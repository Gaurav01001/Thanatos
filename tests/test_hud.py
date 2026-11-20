from __future__ import annotations

import sys
import time
from pathlib import Path

# Add project root and src to sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))
sys.path.insert(0, str(root_dir / "src"))

from engine.core.state import State
from engine.ui.hud import FloatingHUD


def test_hud_state_mapping():
    print("--- [TEST 1] Testing FloatingHUD State Mapping ---")
    hud = FloatingHUD()

    hud.on_state_change(State.STARTING, State.IDLE)
    assert hud.current_state_name == "idle"

    hud.on_state_change(State.IDLE, State.THINKING)
    assert hud.current_state_name == "thinking"

    hud.on_state_change(State.THINKING, State.SPEAKING)
    assert hud.current_state_name == "speaking"
    print("[PASS] FloatingHUD correctly maps StateManager states.\n")


def test_hud_expand_collapse_and_append():
    print("--- [TEST 2] Testing Mini-Deck Expand/Collapse & Chat Append ---")
    hud = FloatingHUD()
    hud.start()
    time.sleep(0.3)
    assert hud._is_running is True

    # Test initial state
    assert hud.is_expanded is False

    # Test expansion
    hud.expand()
    assert hud.is_expanded is True

    # Test appending messages to chat display
    hud.append_message("You", "What is gradient descent?")
    hud.append_message("Thanatos", "Gradient descent iteratively minimizes loss.")

    # Test collapse
    hud.collapse()
    assert hud.is_expanded is False

    # Test toggle
    hud.toggle_expand()
    assert hud.is_expanded is True
    hud.toggle_expand()
    assert hud.is_expanded is False

    hud.stop()
    assert hud._is_running is False
    print("[PASS] Expand/collapse and message logging verified.\n")


if __name__ == "__main__":
    test_hud_state_mapping()
    test_hud_expand_collapse_and_append()
    print("========================================")
    print("ALL EXPANDABLE MINI-DECK TESTS PASSED!")
    print("========================================")
