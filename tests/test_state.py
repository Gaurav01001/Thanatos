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

def test_invalid_transition_raises_error():
    manager = StateManager()

    with pytest.raises(ValueError):
        manager.transition_to(State.EXECUTING)