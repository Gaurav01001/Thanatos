from engine.core.logging import get_logger
from engine.core.state import State, StateManager
from engine.brain.brain import Brain 
from engine.audio.audio import AudioInput
from engine.stt.transcriber import Transcriber
from engine.executor.executor import Executor
from engine.tts.text_to_speech import TextToSpeech
from engine.security.validator import SecurityValidator
from engine.vision.screen import ScreenCapture
from engine.vision.vision import VisionModel

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
    validator = SecurityValidator()
    mode = "text"
    screen = ScreenCapture()
    vision = VisionModel()
    def ask_confirmation() -> bool:
        response = input("Thanatos: Proceed? (yes/no): ").strip().lower()

        return response in ("yes", "y")
    
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
                print("\nThanatos: Glad to assist you!")
                tts.speak("Glad to assist you!")
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
            print("Thanatos: Glad to assist you!")
            tts.speak("Glad to assist you!")
            break

        # ----------------------------------------------------
        # 3. INTENT DETECTION & SECURITY VALIDATION
        # ----------------------------------------------------
        intent = brain.get_intent(message)

        # Validate intent before executing any actions
        status, reason = validator.validate_intent(intent)
        if status == "BLOCKED":
            print(f"Thanatos: {reason}")
            tts.speak(reason)
            continue
        elif status == "CONFIRM":
            print(f"Thanatos: {reason}")
            tts.speak(reason)

            if not ask_confirmation():
                print("Thanatos: Cancelled.")
                tts.speak("Cancelled.")
                continue

        action = intent.get("action")
        target = intent.get("target")
        folder = intent.get("folder")
        

        if action in ("take_screenshot", "analyze_image", "analyze_screen", "look_at_screen"):
            state_manager.transition_to(State.EXECUTING)
            try:
                print("Thanatos: Looking at the screen...")
                tts.speak("Let me take a look")

                #1 capture the screen
                image_path = screen.capture()

                #2 send the screenshot to gemma
                answer = vision.analyze(
                image_path,f"""
                    Look at this computer screenshot and answer the user's question.
                    User's question:
                    {message}
                    Give a concise and accurate answer.
                    Do not ask follow-up questions.
                    Do not describe unrelated parts of the screen.
                    If the requested information cannot be clearly seen, say so.
                    """
                )
                #3 print response
                print(f"Thanatos: {answer}")

                #4 Speak vision 
                tts.speak(answer)
                
            except Exception as e:
                msg = f"Failed to capture screenshot: {e}"
                print(f"Thanatos: {msg}") 
                tts.speak("Failed to capture screenshot")
            state_manager.transition_to(State.IDLE)
            continue
            
        # Open Application
        elif action == "open_application" and target:
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
            success = executor.play_spotify(target)
            if success:
                msg = f"Playing {target} on Spotify"
            else:
                msg = f"I couldn't play {target} on Spotify"
            print(f"Thanatos: {msg}")
            tts.speak(msg)
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
