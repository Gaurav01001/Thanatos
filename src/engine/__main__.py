from engine.core.logging import get_logger
from engine.core.state import State, StateManager
from engine.brain.brain import Brain 
from engine.audio.audio import AudioInput
from engine.stt.transcriber import Transcriber
from engine.executor.executor import Executor
from engine.tts.text_to_speech import TextToSpeech

logger = get_logger("engine")
brain = Brain()

def main() -> None:
    logger.info("Thanatos Starting...")
    state_manager = StateManager()
    logger.info("Current state: %s", state_manager.state.value)
    state_manager.transition_to(State.IDLE)

    # Initialize all subsystems
    executor = Executor()
    audio_input = AudioInput()
    transcriber = Transcriber()
    tts = TextToSpeech()
    mode = "text"

    while state_manager.state == State.IDLE:

        # ----------------------------------------------------
        # 1. INPUT HANDLING (Voice vs Text Mode)
        # ----------------------------------------------------
        if mode == "voice":
            audio = audio_input.record()
            # Pressing Esc cancels voice and returns to text mode
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
                tts.speak("Tataa, byeee!")
                break

            # Pressing Enter on empty prompt switches to Voice Mode
            if user_input == "" or user_input.lower() in ("/v", "/voice"):
                mode = "voice"
                continue

            message = user_input

        # ----------------------------------------------------
        # 2. BUILT-IN TEXT COMMANDS (clear, status, exit)
        # ----------------------------------------------------
        cleaned = message.lower().strip().rstrip(".!?")
        if cleaned == "clear":
            print("Thanatos: Cleared! All memory Erased")
            brain.clear_memory()
            tts.speak("Memory cleared.")
            continue
        elif cleaned == "status":
            print(f"Thanatos State : {state_manager.state.value}")
            tts.speak(f"Current state is {state_manager.state.value}")
            continue
        elif cleaned in ("exit", "quit", "bye", "goodbye"):
            print("Thanatos: Tataa, byeee!")
            tts.speak("Tataa, byeee!")
            break

        # ----------------------------------------------------
        # 3. INTENT DETECTION & ACTION EXECUTION (Open Apps/Files)
        # ----------------------------------------------------
        intent = brain.get_intent(message)
        action = intent.get("action")
        target = intent.get("target")
        folder = intent.get("folder")

        # Open Application
        if action == "open_application" and target:
            state_manager.transition_to(State.EXECUTING)
            success = executor.open_application(target)
            if success:
                msg = f"Opened {target}"
                print(f"Thanatos: {msg}")
                tts.speak(msg)
            else:
                msg = f"Could not find or open {target}"
                print(f"Thanatos: {msg}")
                tts.speak(msg)
            state_manager.transition_to(State.IDLE)
            continue

        # Open File
        elif action == "open_file" and target:
            state_manager.transition_to(State.EXECUTING)
            success = executor.open_file(target, folder_hint=folder)
            if success:
                msg = f"Opened {target}"
                print(f"Thanatos: {msg}")
                tts.speak(msg)
            else:
                msg = f"Could not find file {target}"
                print(f"Thanatos: {msg}")
                tts.speak(msg)
            state_manager.transition_to(State.IDLE)
            continue

        # Play Music on Spotify
        elif action == "play_music" and target:
            state_manager.transition_to(State.EXECUTING)
            msg = f"Playing {target} on Spotify"
            print(f"Thanatos: {msg}")
            tts.speak(msg)
            executor.play_spotify(target)
            state_manager.transition_to(State.IDLE)
            continue

        # ----------------------------------------------------
        # 4. CHAT CONVERSATION (Brain LLM + Voice Output)
        # ----------------------------------------------------
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

        # Erase "Thanatos: Thinking..." before printing & speaking
        print("\r" + " " * 30 + "\r", end="", flush=True)
        print(f"Thanatos: {response}")
        tts.speak(response)

if __name__ == "__main__": 
    main()
