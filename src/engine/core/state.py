from enum import Enum
from engine.core.logging import get_logger

class State(Enum): #enum gives us controlled variables
    #Core states enum gives us controlled variables 
    STARTING = "starting"
    #IDLE means nothing is happeneing
    IDLE = "idle"
    #Running means the AI is doing something
    # RUNNING = "running"
    #Listening means the AI is listening for user input
    LISTENING = "listening"
    #AI States
    TRANSCRIBING = "transcribing"
    THINKING = "thinking"
    EXECUTING = "executing"
    ERROR = "error"
    
    #state -> defines the vocab
    #statemanager  -> manages the vocab

class StateManager:
    _allowed_transitions = {
        State.STARTING: {State.IDLE, State.ERROR},#im currently in starting im allowed to go idle or error
        State.IDLE: {State.LISTENING, State.ERROR},
        State.LISTENING: {State.TRANSCRIBING, State.ERROR},
        State.TRANSCRIBING: {State.THINKING, State.ERROR},
        State.THINKING: {State.EXECUTING, State.ERROR},
        State.EXECUTING: {State.IDLE, State.ERROR},
        State.ERROR: {State.IDLE},
    }#none means this function is supposed to return nothing 
    def __init__(self) -> None: #intilizing the state when manager is created 
        self._state = State.STARTING
        self._logger = get_logger(__name__)

    @property
    def state(self) -> State:
        return self._state

    def transition_to(self, new_state: State) -> None:
        allowed_states = self._allowed_transitions[self._state]

        if new_state not in allowed_states:
            raise ValueError(f"Invalid transition : {self._state.value} -> {new_state.value}")

        
        #logging the state transition
        self._logger.info("State Transition: %s->%s",
                            self._state.value,
                            new_state.value)
        self._state = new_state



#StateManager()
#     ↓
# __init__()
#     ↓
# this manager's state = STARTING

# manager.state
#     ↓
# @property state()
#     ↓
# return self._state
#     ↓
# "Here's my current state."

# manager.transition_to(State.IDLE)
#     ↓
# check allowed transitions
#     ↓
# if allowed
#     ↓
# self._state = State.IDLE

