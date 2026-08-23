from engine.core.logging import get_logger
from engine.core.state import State , StateManager
from engine.brain.brain import Brain 
from engine.audio.audio import AudioInput
from engine.stt.transcriber import Transcriber

logger = get_logger("engine")
brain = Brain()

def main()-> None:
    logger.info("Thanatos Starting...")
    state_manager = StateManager()
    logger.info("Current state: %s", state_manager.state.value)
    state_manager.transition_to(State.IDLE)

    audio_input = AudioInput()
    transcriber = Transcriber()
    mode = "text"

    while state_manager.state == State.IDLE:
        if mode == "voice":
            audio = audio_input.record()
            # Esc was pressed: switch back to text mode
            if audio is None:
                mode = "text"
                continue

            if len(audio) == 0:
                continue

            message = transcriber.transcribe(audio)
            if not message.strip():
                continue

            print(f"You (Voice): {message}")
        else:
            try:
                user_input = input("You: ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\nThanatos: Tataa, byeee!")
                break

            # If user pressed Enter without typing (or typed /v), switch to Voice Mode
            if user_input == "" or user_input.lower() in ("/v", "/voice"):
                mode = "voice"
                continue

            message = user_input
        
        # to clear chat memory
        cleaned = message.lower().strip().rstrip(".!?")
        if cleaned == "clear":
            print("Thanatos: Cleared! All memory Erasad")
            brain.clear_memory()
            continue
        # to show which state thanatos is 
        elif cleaned == "status":
            print(f"Thanatos State : {state_manager.state.value}")
            continue
        # to exit
        elif cleaned in ("exit", "quit", "bye", "goodbye"):
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
