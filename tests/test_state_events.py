from __future__ import annotations

import sys
from pathlib import Path

# Add project root and src to sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))
sys.path.insert(0, str(root_dir / "src"))

from engine.core.state import State, StateManager


def test_state_event_subscriber():
    print("--- [TEST 1] Testing StateManager Event Subscriber ---")
    sm = StateManager()

    transitions_recorded = []

    def on_change(old_state: State, new_state: State):
        transitions_recorded.append((old_state, new_state))
        print(f"Event: {old_state.value} -> {new_state.value}")

    sm.subscribe(on_change)

    # 1. Starting -> Idle
    sm.transition_to(State.IDLE)
    assert sm.state == State.IDLE

    # 2. Idle -> Thinking
    sm.transition_to(State.THINKING)
    assert sm.state == State.THINKING

    # 3. Thinking -> Speaking (NEW STATE)
    sm.transition_to(State.SPEAKING)
    assert sm.state == State.SPEAKING

    # 4. Speaking -> Idle
    sm.transition_to(State.IDLE)
    assert sm.state == State.IDLE

    expected = [
        (State.STARTING, State.IDLE),
        (State.IDLE, State.THINKING),
        (State.THINKING, State.SPEAKING),
        (State.SPEAKING, State.IDLE),
    ]
    assert transitions_recorded == expected, f"Recorded transitions mismatch: {transitions_recorded}"
    print("[PASS] StateManager subscriber notified for all state transitions.\n")


def test_invalid_transition():
    print("--- [TEST 2] Testing Invalid Transition Safety ---")
    sm = StateManager()
    sm.transition_to(State.IDLE)

    # Attempting to jump directly from IDLE to SPEAKING should be blocked
    try:
        sm.transition_to(State.SPEAKING)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        print(f"Correctly caught invalid transition: {e}")
        print("[PASS] State validation holds firm.\n")


if __name__ == "__main__":
    test_state_event_subscriber()
    test_invalid_transition()
    print("========================================")
    print("ALL STEP 1 STATE EVENT TESTS PASSED!")
    print("========================================")
