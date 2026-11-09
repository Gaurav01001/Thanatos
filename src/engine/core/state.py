from __future__ import annotations

from collections.abc import Callable
from enum import Enum
from typing import ClassVar

from engine.core.logging import get_logger


class State(Enum):
    STARTING = "starting"
    IDLE = "idle"
    LISTENING = "listening"
    TRANSCRIBING = "transcribing"
    THINKING = "thinking"
    EXECUTING = "executing"
    SPEAKING = "speaking"
    ERROR = "error"


class StateManager:
    _allowed_transitions: ClassVar[dict[State, set[State]]] = {
        State.STARTING: {State.IDLE, State.ERROR},
        State.IDLE: {State.LISTENING, State.THINKING, State.EXECUTING, State.ERROR},
        State.LISTENING: {State.TRANSCRIBING, State.IDLE, State.ERROR},
        State.TRANSCRIBING: {State.THINKING, State.EXECUTING, State.IDLE, State.ERROR},
        State.THINKING: {State.EXECUTING, State.SPEAKING, State.IDLE, State.ERROR},
        State.EXECUTING: {State.THINKING, State.SPEAKING, State.IDLE, State.LISTENING, State.ERROR},
        State.SPEAKING: {State.IDLE, State.LISTENING, State.ERROR},
        State.ERROR: {State.IDLE},
    }

    def __init__(self) -> None:
        self._state = State.STARTING
        self._logger = get_logger(__name__)
        self._listeners: list[Callable[[State, State], None]] = []

    @property
    def state(self) -> State:
        return self._state

    def subscribe(self, callback: Callable[[State, State], None]) -> None:
        """Register a callback function: callback(old_state, new_state)."""
        self._listeners.append(callback)

    def transition_to(self, new_state: State) -> None:
        if new_state == self._state:
            return

        allowed_states = self._allowed_transitions[self._state]

        if new_state not in allowed_states:
            raise ValueError(f"Invalid transition: {self._state.value} -> {new_state.value}")

        old_state = self._state
        self._logger.debug("State Transition: %s -> %s", old_state.value, new_state.value)
        self._state = new_state

        # Broadcast state change to all subscribers (HUD pill, tray icon, etc.)
        for listener in self._listeners:
            try:
                listener(old_state, new_state)
            except Exception as e:  # noqa: BLE001
                self._logger.warning("Listener error during transition: %s", e)
