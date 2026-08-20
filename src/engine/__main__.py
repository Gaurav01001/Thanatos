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

        if message.lower() == "exit":
            print("Thanatos: Tataa, byeee!")
            break

        response = brain.respond(message)
        print(f"Thanatos: {response}")

if __name__ == "__main__": 
    main()
