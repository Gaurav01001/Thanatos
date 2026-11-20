import pytest

from engine.core.state import State, StateManager


def test_initial_state_is_starting():
    manager = StateManager()
    assert manager.state == State.STARTING

def test_state_can_change():
    manager = StateManager()
    manager.transition_to(State.IDLE)
    assert manager.state == State.IDLE  

def test_valid_transition():
    manager = StateManager()
    manager.transition_to(State.IDLE)
    manager.transition_to(State.LISTENING) 
    assert manager.state == State.LISTENING

def test_thinking_transitions():
    manager = StateManager()
    manager.transition_to(State.IDLE)
    manager.transition_to(State.THINKING)
    assert manager.state == State.THINKING
    manager.transition_to(State.IDLE)
    assert manager.state == State.IDLE

def test_invalid_transition_raises_error():
    manager = StateManager()

    with pytest.raises(ValueError):
        manager.transition_to(State.EXECUTING)


def test_transcribing_and_executing_transitions():
    manager = StateManager()
    manager.transition_to(State.IDLE)
    manager.transition_to(State.LISTENING)
    manager.transition_to(State.TRANSCRIBING)

    # Transcribing can transition directly to EXECUTING or THINKING or IDLE
    manager.transition_to(State.EXECUTING)
    assert manager.state == State.EXECUTING

    manager.transition_to(State.SPEAKING)
    assert manager.state == State.SPEAKING

    manager.transition_to(State.IDLE)
    assert manager.state == State.IDLE