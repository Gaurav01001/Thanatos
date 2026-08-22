from engine.core.logging import get_logger
from engine.core.state import State , StateManager
from engine.brain.brain import Brain 
logger = get_logger("engine")
brain = Brain()

def main()-> None:
    logger.info("Thanatos Starting...")
    state_manager = StateManager()
    logger.info("Current state: %s", state_manager.state.value)
    state_manager.transition_to(State.IDLE)

    while state_manager.state == State.IDLE:
        message = input("You: ")
        # to clear chat memory
        if message.lower() == "clear":
            print("Thanatos: Cleared! All memory Erasad")
            brain.clear_memory()
            continue
        # to show which state thanatos is 
        elif message.lower() == "status":
            print(f"Thanatos State : {state_manager.state.value}")
            continue
        # to exit
        elif message.lower() == "exit":
            print("Thanatos: Tataa, byeee!")
            break
        # To change state from IDLE to BUSY
        state_manager.transition_to(State.THINKING)
        print("Thanatos: Thinking...", end="", flush=True)
        try:
            response = brain.respond(message)
            state_manager.transition_to(State.IDLE)
        except Exception as e:
            state_manager.transition_to(State.ERROR)
            print(f"Thanatos: Something went wrong: {e}")
            state_manager.transition_to(State.IDLE)
            continue
        # Erase "Thanatos: Thinking..." before printing the response
        print("\r" + " " * 30 + "\r", end="", flush=True)
        print(f"Thanatos: {response}")
if __name__ == "__main__": 
    main()
