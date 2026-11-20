from __future__ import annotations

import queue
import sys
import threading
import time
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001, S110
    pass

from engine.audio.audio import AudioInput, is_exit_command, is_sleep_command, is_wake_command, play_chime
from engine.audio.clap import ClapDetector
from engine.audio.wake import WakeWordDetector
from engine.brain.brain import Brain
from engine.browser.browser_agent import BrowserAgent
from engine.core.hotkey import HotkeyManager
from engine.core.logging import get_logger
from engine.core.ollama_service import ensure_ollama_running, is_ollama_running
from engine.core.state import State, StateManager
from engine.executor.executor import Executor
from engine.security.validator import SecurityValidator
from engine.stt.transcriber import Transcriber
from engine.tts.text_to_speech import TextToSpeech
from engine.ui.hud import FloatingHUD
from engine.ui.tray import SystemTrayApp
from engine.vision.mentor import DSAMentor
from engine.vision.screen import ScreenCapture
from engine.vision.vision import VisionModel

logger = get_logger("engine")
brain: Brain | None = None


def main() -> None:
    # ----------------------------------------------------
    # CLI Argument Flags (e.g. thanatos --version, --check, --help)
    # ----------------------------------------------------
    args = sys.argv[1:]
    if args:
        first = args[0].lower().strip()
        if first in ("--version", "-v", "version"):
            print("Thanatos AI Desktop Companion v0.1.0")
            print(f"Python: {sys.version.split()[0]}")
            sys.exit(0)

        if first in ("--help", "-h", "help"):
            print("======================================================")
            print("       THANATOS AI DESKTOP COMPANION                  ")
            print("======================================================")
            print("\nUsage:")
            print("  thanatos            Launch the interactive companion")
            print("  thanatos --check    Run diagnostic health checks on models & audio")
            print("  thanatos --version  Display installed version")
            print("  thanatos --help     Show this command-line manual")
            print("\nControls & Hotkeys:")
            print("  Ctrl+Space          Toggle Tokyo Night Mini-Deck HUD")
            print("  F8                  Capture screen for Socratic DSA Mentor")
            print("  Ctrl+Shift+V        Instant Clipboard Smart Fix & Polish")
            print("  Say 'Wake up'       Hands-free voice recognition mode")
            print("  Say 'Go to sleep'   Rest / text-only standby")
            print("  Type 'clear'        Reset conversation context")
            print("  Type 'exit'         Shut down assistant safely")
            sys.exit(0)

        if first in ("--check", "-c", "check", "doctor"):
            print("======================================================")
            print("       THANATOS SYSTEM HEALTH DIAGNOSTICS             ")
            print("======================================================")
            # 1. Ollama service check
            ollama_ok = is_ollama_running() or ensure_ollama_running(timeout=3.0)
            status_str = "[OK] Active and responding" if ollama_ok else "[X] Failed to connect"
            print(f"Ollama Server:      {status_str}")

            # 2. SQLite User Memory check
            try:
                from engine.memory.user_memory import UserMemory
                mem = UserMemory()
                all_m = mem.get_all_memories()
                p_count = len(all_m.get("profile", {}))
                n_count = len(all_m.get("notes", []))
                print(f"SQLite User Memory: [OK] Connected ({p_count} profile facts, {n_count} notes stored)")
            except Exception as e:
                print(f"SQLite User Memory: [X] Error: {e}")

            # 3. Piper TTS Voice check
            root_dir = Path(__file__).resolve().parents[2]
            ryan_path = root_dir / "en_US-ryan-medium.onnx"
            if ryan_path.exists():
                print("Piper TTS Voice:    [OK] Model 'en_US-ryan-medium.onnx' verified")
            else:
                print("Piper TTS Voice:    [!] Voice file missing at root")

            # 4. Playwright Browser Automation check
            try:
                b_check = BrowserAgent(headless=True)
                b_check.close()
                print("Playwright Browser: [OK] Chromium automation driver ready")
            except Exception as e:
                print(f"Playwright Browser: [!] Warning: {e}")

            print("======================================================")
            print("All core subsystems are verified. Type 'thanatos' to start.")
            sys.exit(0)

    logger.info("Thanatos Starting...")
    global brain
    brain = Brain()

    # Ensure Ollama LLM backend is accessible before servicing queries
    if not is_ollama_running():
        logger.info("Ollama is not running. Launching background Ollama server...")
        print("Thanatos: Initializing local Ollama server in background...", end="", flush=True)
        if ensure_ollama_running(timeout=15.0):
            print("\rThanatos: Local Ollama server connected and ready.         \n", flush=True)
            logger.info("Ollama server connected successfully.")
        else:
            print("\rThanatos: Warning: Could not connect to Ollama.            \n", flush=True)
            logger.warning("Could not auto-start Ollama server. Check your Ollama installation.")

    state_manager = StateManager()
    logger.info("Current state: %s", state_manager.state.value)
    state_manager.transition_to(State.IDLE)

    # Initialize core subsystems
    executor = Executor()
    audio_input = AudioInput()
    transcriber = Transcriber()
    tts = TextToSpeech()
    validator = SecurityValidator()
    screen = ScreenCapture()
    vision = VisionModel()
    dsa_mentor = DSAMentor()
    browser_agent = BrowserAgent()

    event_queue: queue.Queue[dict] = queue.Queue()
    mode = "text"
    is_muted = False
    is_running = True

    def speak(text: str) -> None:
        if not is_muted and text:
            tts.speak(text)

    def on_mute_toggle() -> bool:
        nonlocal is_muted
        is_muted = not is_muted
        logger.info("Audio mute toggled to: %s", is_muted)
        return is_muted

    def on_voice_toggle() -> None:
        nonlocal mode
        if mode == "voice":
            mode = "text"
            play_chime("sleep")
            hud.append_message("System", "Voice mode disabled. Say 'Wake up' or click 🎙️ to resume.")
            print("\nThanatos: Voice mode disabled. Back to standby mode.")
            state_manager.transition_to(State.IDLE)
            wake_detector.resume()
            clap_detector.resume()
        else:
            mode = "voice"
            play_chime("wake")
            hud.append_message("System", "🎙️ Hands-free voice active. Speak naturally or say 'Go to sleep'.")
            event_queue.put({"type": "voice_wake"})

    def on_wake_detected(trigger: str = "") -> None:
        logger.info("Wake directive triggered (%s) -> waking Thanatos into voice mode", trigger)
        event_queue.put({"type": "voice_wake", "trigger": trigger})

    def on_upload_file(filepath: str) -> str:
        state_manager.transition_to(State.EXECUTING)
        try:
            res = brain.index_document(filepath)
            speak("Document indexed successfully.")
            state_manager.transition_to(State.IDLE)
            return res
        except Exception as e:  # noqa: BLE001
            state_manager.transition_to(State.IDLE)
            return f"Error indexing document: {e}"

    def on_submit_query(query: str) -> None:
        event_queue.put({"type": "query", "text": query, "source": "hud"})

    def ask_confirmation() -> bool:
        try:
            response = input("Thanatos: Proceed? (yes/no): ").strip().lower()
            return response in ("yes", "y")
        except (KeyboardInterrupt, EOFError):
            return False

    # Initialize Spoken Wake Word Listener ("Wake up", "Hey Thanatos")
    wake_detector = WakeWordDetector(transcriber=transcriber, on_wake=lambda text: on_wake_detected(f"spoken: {text}"))
    wake_detector.start()

    # Initialize Acoustic Double-Clap Listener as secondary wake
    clap_detector = ClapDetector(on_double_clap=lambda: on_wake_detected("double-clap"))
    clap_detector.start()

    # Initialize Stage 4 & 4.5 UI Subsystems (Floating Mini-Deck, Tray, and Global Hotkeys)
    tray_app = SystemTrayApp(
        on_mute_toggle=on_mute_toggle,
        on_quit=lambda: event_queue.put({"type": "exit"}),
    )
    hud = FloatingHUD(
        on_click=None,
        on_mute_toggle=on_mute_toggle,
        on_voice_toggle=on_voice_toggle,
        on_upload_file=on_upload_file,
        on_submit_query=on_submit_query,
    )
    hud.on_click = hud.toggle_expand

    state_manager.subscribe(hud.on_state_change)
    state_manager.subscribe(tray_app.on_state_change)

    hud.start()
    tray_app.start()

    # Ctrl+Space summons the Mini-Deck; F8 triggers Vision DSA Mentor; Ctrl+Shift+V triggers Clipboard Smart Fix
    hotkey = HotkeyManager(
        on_trigger=hud.toggle_expand,
        on_vision_trigger=lambda: event_queue.put({
            "type": "vision_mentor",
            "source": "hotkey",
            "query": "give me a hint",
            "mode": "hint",
        }),
        on_clipboard_trigger=lambda: event_queue.put({
            "type": "clipboard_fix",
            "source": "hotkey",
        }),
    )
    hotkey.start()

    def shutdown_ui() -> None:
        wake_detector.stop()
        clap_detector.stop()
        hud.stop()
        tray_app.stop()
        hotkey.stop()
        browser_agent.close()

    def process_clipboard_fix(source: str = "hotkey") -> None:
        """
        Stage 10: Clipboard Intelligence & Smart Fix.
        Reads clipboard, auto-classifies content, fixes/polishes it,
        writes clean output back to clipboard, displays diff card, and whispers punchline.
        """
        state_manager.transition_to(State.EXECUTING)
        try:
            from engine.clipboard.smart_fix import get_clipboard_text, set_clipboard_text

            text = get_clipboard_text()
            if not text:
                msg = "Clipboard is empty or does not contain readable text."
                print(f"\nThanatos: {msg}")
                hud.append_message("Thanatos", msg)
                if not is_muted:
                    state_manager.transition_to(State.SPEAKING)
                    speak(msg)
                state_manager.transition_to(State.IDLE)
                return

            print(f"\nThanatos: Analyzing clipboard text ({len(text)} chars)...")
            hud.append_message("Thanatos", "Analyzing clipboard content...")
            if not is_muted:
                speak("Analyzing clipboard.")

            state_manager.transition_to(State.THINKING)
            result = brain.fix_clipboard_content(text)

            # Auto-update clipboard with the fixed text so user can immediately paste (Ctrl+V)
            if result.fixed_text:
                set_clipboard_text(result.fixed_text)

            # Format dual-track visual preview card
            preview_card = (
                f"📋 Clipboard Smart Fix [{result.content_type.upper()}]\n"
                f"{'-'*45}\n"
                f"Diagnosis: {result.explanation}\n\n"
                f"Fixed / Polished Output (Copied to Clipboard):\n"
                f"{result.fixed_text}\n"
                f"{'-'*45}"
            )
            print(f"\n{preview_card}\n")
            hud.append_message("Thanatos (Smart Fix)", preview_card)

            if not is_muted and result.speech_text:
                state_manager.transition_to(State.SPEAKING)
                speak(result.speech_text)

        except Exception as e:  # noqa: BLE001
            err_msg = f"Clipboard Smart Fix error: {e}"
            print(f"Thanatos: {err_msg}")
            hud.append_message("Thanatos", err_msg)
        finally:
            state_manager.transition_to(State.IDLE)

    def process_vision_mentor(query: str = "", mode: str = "hint", source: str = "hotkey") -> None:
        """Captures screen and triggers Socratic DSA mentor guidance with dual-track output."""
        state_manager.transition_to(State.EXECUTING)
        try:
            print("\nThanatos: Capturing screen for DSA analysis...")
            hud.append_message("Thanatos", "Analyzing code on your screen...")
            if not is_muted:
                speak("Analyzing your code.")

            # 1. Capture screen silently
            image_path = screen.capture()

            # 2. Analyze with DSAMentor
            state_manager.transition_to(State.THINKING)
            res = dsa_mentor.analyze_screen(image_path, query=query, mode=mode)

            # 3. Print technical card to terminal & Mini-Deck
            print(f"\n{res.display_text}\n")
            hud.append_message("Thanatos (Mentor)", res.display_text)

            # 4. Whisper the 1-2 sentence Socratic nudge into headphones
            if not is_muted and res.speech_text:
                state_manager.transition_to(State.SPEAKING)
                speak(res.speech_text)

        except Exception as e:  # noqa: BLE001
            err_msg = f"DSA Mentor error: {e}"
            print(f"Thanatos: {err_msg}")
            hud.append_message("Thanatos", err_msg)
        finally:
            state_manager.transition_to(State.IDLE)

    def process_user_message(message: str, source: str = "text") -> None:
        nonlocal is_muted, mode, is_running

        if not message.strip():
            return

        cleaned = message.lower().strip().rstrip(".!?")

        # ----------------------------------------------------
        # 1. BUILT-IN COMMANDS & CONVERSATIONAL SLEEP
        # ----------------------------------------------------
        if cleaned == "clear":
            print("Thanatos: Cleared! All memory Erased")
            hud.append_message("Thanatos", "Memory cleared.")
            brain.clear_memory()
            speak("Memory cleared.")
            return

        if cleaned == "status":
            msg = f"Current state is {state_manager.state.value}"
            print(f"Thanatos State: {state_manager.state.value}")
            hud.append_message("Thanatos", msg)
            speak(msg)
            return

        if cleaned in ("mute", "/mute", "silent", "/silent"):
            is_muted = True
            print("Thanatos: Audio muted. Text-only display mode active.")
            hud.append_message("Thanatos", "Audio muted.")
            return

        if cleaned in ("unmute", "/unmute", "voice", "/voice"):
            is_muted = False
            print("Thanatos: Audio unmuted. Voice mode active.")
            hud.append_message("Thanatos", "Audio active.")
            speak("Audio is now active.")
            return

        if cleaned.startswith("say "):
            spoken = message[4:].strip()
            print(f"Thanatos: {spoken}")
            hud.append_message("Thanatos", spoken)
            speak(spoken)
            return

        # Spoken Wake Word Command (e.g. "Wake up", "Hey Thanatos")
        if is_wake_command(message):
            wake_reply = "I am awake and listening. How can I assist you?"
            mode = "voice"
            print(f"Thanatos: {wake_reply}")
            hud.append_message("Thanatos", wake_reply)
            play_chime("wake")
            speak("Awake and listening.")
            state_manager.transition_to(State.IDLE)
            wake_detector.pause()
            clap_detector.pause()
            return

        # Conversational Sleep Command: "Go to sleep", "I'm not talking to you", "That's all"
        if is_sleep_command(message):
            sleep_reply = "Going to sleep. Say 'Wake up' or press Ctrl+Space when you need me."
            print(f"Thanatos: {sleep_reply}")
            hud.append_message("Thanatos", sleep_reply)
            play_chime("sleep")
            speak("Going to sleep.")
            mode = "text"
            state_manager.transition_to(State.IDLE)
            wake_detector.resume()
            clap_detector.resume()
            return

        # Conversational Exit Command: "exit", "quit", "close assistant", "terminate", etc.
        if is_exit_command(message):
            farewell = "Glad to assist you! Shutting down Thanatos."
            print(f"Thanatos: {farewell}")
            hud.append_message("Thanatos", farewell)
            play_chime("sleep")
            if (mode == "voice" or source == "voice") and not is_muted:
                speak("Glad to assist you. Goodbye.")
            is_running = False
            return

        # ----------------------------------------------------
        # 2. INTENT DETECTION & SECURITY VALIDATION
        # ----------------------------------------------------
        intent = brain.get_intent(message)
        status, reason = validator.validate_intent(intent)
        if status == "BLOCKED":
            print(f"Thanatos: {reason}")
            hud.append_message("Thanatos", reason)
            speak(reason)
            return
        elif status == "CONFIRM":
            print(f"Thanatos: {reason}")
            hud.append_message("Thanatos", f"Confirmation required: {reason}")
            speak(reason)
            if not ask_confirmation():
                print("Thanatos: Cancelled.")
                hud.append_message("Thanatos", "Cancelled.")
                speak("Cancelled.")
                return

        action = intent.get("action")
        target = intent.get("target")
        folder = intent.get("folder")

        # ----------------------------------------------------
        # 3. ACTION DISPATCH (Vision, Apps, Files, RAG, Spotify, Typing)
        # ----------------------------------------------------
        if action == "dsa_mentor":
            process_vision_mentor(
                query=target or message,
                mode=folder or "hint",
                source=source,
            )
            return

        # ----------------------------------------------------
        # Clipboard Intelligence & Smart Fix (Stage 10)
        # ----------------------------------------------------
        if action == "smart_fix_clipboard":
            process_clipboard_fix(source=source)
            return

        # ----------------------------------------------------
        # Generic Browser Automation Primitives (Stage 7 & Stage 12 Guard)
        # ----------------------------------------------------
        if action in ("browse_url", "browse_web"):
            msg_lower = message.lower()
            is_explicit_browser = (
                action == "browse_url"
                or any(kw in msg_lower for kw in ("browser", "chrome", "firefox", "edge", "in web browser", "open web"))
            )
            if not is_explicit_browser:
                logger.info(
                    "Query '%s' redirected from physical browser popup to cognitive live web grounding.",
                    message,
                )
            else:
                state_manager.transition_to(State.EXECUTING)
                target_str = target or message
                action_desc = "Navigating to website..." if action == "browse_url" else "Searching web via browser..."
                print(f"\nThanatos: {action_desc}")
                hud.append_message("Thanatos", action_desc)
                if (mode == "voice" or source == "voice") and not is_muted:
                    speak("Browsing web for you.")

                try:
                    res = browser_agent.quick_browse(target_str)
                    summary_text = res.get("summary", "Browser action completed.")
                    print(f"\nThanatos (Browser):\n{'-'*45}\n{summary_text}\n{'-'*45}\n")
                    hud.append_message("Thanatos (Browser)", summary_text)

                    if (mode == "voice" or source == "voice") and not is_muted:
                        state_manager.transition_to(State.SPEAKING)
                        title = res.get("title")
                        speech_msg = f"I've opened {title} in the browser." if title else "Browser task completed."
                        speak(speech_msg)
                except Exception as e:  # noqa: BLE001
                    err_msg = f"Browser error: {e}"
                    print(f"Thanatos: {err_msg}")
                    hud.append_message("Thanatos", err_msg)
                    if (mode == "voice" or source == "voice") and not is_muted:
                        state_manager.transition_to(State.SPEAKING)
                        speak("Browser encountered an error.")
                state_manager.transition_to(State.IDLE)
                return

        if action in ("take_screenshot", "analyze_image", "analyze_screen", "look_at_screen"):
            state_manager.transition_to(State.EXECUTING)
            try:
                print("Thanatos: Looking at the screen...")
                hud.append_message("Thanatos", "Looking at your screen...")
                speak("Let me take a look")
                image_path = screen.capture()
                answer = vision.analyze(
                    image_path,
                    f"Look at this computer screenshot and answer the user's question.\n"
                    f"User's question:\n{message}\n"
                    f"Give a concise and accurate answer.\n"
                    f"Do not ask follow-up questions.\n"
                    f"Do not describe unrelated parts of the screen.\n"
                    f"If the requested information cannot be clearly seen, say so.",
                )
                print(f"Thanatos: {answer}")
                hud.append_message("Thanatos", answer)
                speak(answer)
            except Exception as e:  # noqa: BLE001
                msg = f"Failed to capture screenshot: {e}"
                print(f"Thanatos: {msg}")
                hud.append_message("Thanatos", msg)
                speak("Failed to capture screenshot")
            state_manager.transition_to(State.IDLE)
            return

        if action == "open_application" and target:
            state_manager.transition_to(State.EXECUTING)
            success = executor.open_application(target)
            msg = f"Opened {target}" if success else f"Could not find or open {target}"
            print(f"Thanatos: {msg}")
            hud.append_message("Thanatos", msg)
            if (mode == "voice" or source == "voice") and not is_muted:
                state_manager.transition_to(State.SPEAKING)
                speak(msg)
            state_manager.transition_to(State.IDLE)
            return

        if action == "open_file" and target:
            state_manager.transition_to(State.EXECUTING)
            success = executor.open_file(target, folder_hint=folder)
            msg = f"Opened {target}" if success else f"Could not find file {target}"
            print(f"Thanatos: {msg}")
            hud.append_message("Thanatos", msg)
            if (mode == "voice" or source == "voice") and not is_muted:
                state_manager.transition_to(State.SPEAKING)
                speak(msg)
            state_manager.transition_to(State.IDLE)
            return

        if action == "index_document":
            if not target:
                msg = "Please provide a valid file path to index."
                print(f"Thanatos: {msg}")
                hud.append_message("Thanatos", msg)
                speak(msg)
                return

            state_manager.transition_to(State.EXECUTING)
            print("Thanatos: Indexing document...")
            hud.append_message("Thanatos", f"Indexing: {target}...")
            if (mode == "voice" or source == "voice") and not is_muted:
                speak("Indexing document...")
            try:
                result = brain.index_document(target)
                print(f"Thanatos: {result}")
                hud.append_message("Thanatos", result)
                if (mode == "voice" or source == "voice") and not is_muted:
                    state_manager.transition_to(State.SPEAKING)
                    speak(result)
            except Exception as e:  # noqa: BLE001
                msg = f"Failed to index document: {e}"
                print(f"Thanatos: {msg}")
                hud.append_message("Thanatos", msg)
            state_manager.transition_to(State.IDLE)
            return

        if action == "play_music" and target:
            state_manager.transition_to(State.EXECUTING)
            success = executor.play_spotify(target)
            msg = f"Playing {target} on Spotify" if success else f"I couldn't play {target} on Spotify"
            print(f"Thanatos: {msg}")
            hud.append_message("Thanatos", msg)
            if (mode == "voice" or source == "voice") and not is_muted:
                state_manager.transition_to(State.SPEAKING)
                speak(msg)
            state_manager.transition_to(State.IDLE)
            return

        # ----------------------------------------------------
        # Desktop Typing & Safe Writing Automation (Stage 5)
        # ----------------------------------------------------
        if action == "write_text":
            state_manager.transition_to(State.THINKING)
            prompt_to_draft = target or message
            print("Thanatos: Drafting text...", end="", flush=True)
            hud.append_message("Thanatos", "Drafting text...")
            if (mode == "voice" or source == "voice") and not is_muted:
                speak("Drafting that for you.")

            try:
                draft = brain.draft_text(prompt_to_draft)
            except Exception as e:  # noqa: BLE001
                draft = prompt_to_draft
                logger.warning("Error drafting text: %s", e)

            # Clear "Drafting text..." line
            print("\r" + " " * 30 + "\r", end="", flush=True)
            print(f"Thanatos (Draft Preview):\n{'-'*40}\n{draft}\n{'-'*40}")
            hud.append_message("Thanatos", f"Draft Preview:\n{draft}")

            state_manager.transition_to(State.EXECUTING)
            time.sleep(0.3)
            success = executor.paste_text(draft)

            if success:
                msg = "Draft typed into your active window."
                print(f"Thanatos: {msg}")
                hud.append_message("Thanatos", msg)
                if (mode == "voice" or source == "voice") and not is_muted:
                    state_manager.transition_to(State.SPEAKING)
                    speak(msg)
            else:
                msg = "Failed to paste text into the active window."
                print(f"Thanatos: {msg}")
                hud.append_message("Thanatos", msg)
                if (mode == "voice" or source == "voice") and not is_muted:
                    state_manager.transition_to(State.SPEAKING)
                    speak(msg)

            state_manager.transition_to(State.IDLE)
            return

        if action == "paste_text":
            state_manager.transition_to(State.EXECUTING)
            text_to_paste = target or message
            time.sleep(0.2)
            success = executor.paste_text(text_to_paste)
            msg = "Text pasted." if success else "Failed to paste text."
            print(f"Thanatos: {msg}")
            hud.append_message("Thanatos", msg)
            if (mode == "voice" or source == "voice") and not is_muted:
                state_manager.transition_to(State.SPEAKING)
                speak(msg)
            state_manager.transition_to(State.IDLE)
            return

        if action in ("send_email", "send_message"):
            state_manager.transition_to(State.EXECUTING)
            msg = f"Simulated dispatch for '{action}': {target}. (Safe simulation gate)."
            print(f"Thanatos: {msg}")
            hud.append_message("Thanatos", msg)
            if (mode == "voice" or source == "voice") and not is_muted:
                state_manager.transition_to(State.SPEAKING)
                speak("External dispatch confirmed and simulated safely.")
            state_manager.transition_to(State.IDLE)
            return

        # ----------------------------------------------------
        # 3-Tier Persistent Memory (Stage 8)
        # ----------------------------------------------------
        if action == "save_memory":
            state_manager.transition_to(State.EXECUTING)
            target_str = target or message
            res = brain.save_user_memory(target_str, folder=folder)
            print(f"Thanatos: {res}")
            hud.append_message("Thanatos", res)
            if (mode == "voice" or source == "voice") and not is_muted:
                state_manager.transition_to(State.SPEAKING)
                speak(res)
            state_manager.transition_to(State.IDLE)
            return

        if action == "recall_memory":
            state_manager.transition_to(State.EXECUTING)
            res = brain.recall_user_memory(target)
            print(f"Thanatos:\n{res}")
            hud.append_message("Thanatos", res)
            if (mode == "voice" or source == "voice") and not is_muted:
                state_manager.transition_to(State.SPEAKING)
                summary = brain._create_spoken_summary(res)
                speak(summary)
            state_manager.transition_to(State.IDLE)
            return

        if action == "delete_memory":
            state_manager.transition_to(State.EXECUTING)
            target_str = target or message
            res = brain.delete_user_memory(target_str)
            print(f"Thanatos: {res}")
            hud.append_message("Thanatos", res)
            if (mode == "voice" or source == "voice") and not is_muted:
                state_manager.transition_to(State.SPEAKING)
                speak(res)
            state_manager.transition_to(State.IDLE)
            return

        if action == "wipe_memory":
            state_manager.transition_to(State.EXECUTING)
            res = brain.wipe_user_memory()
            print(f"Thanatos: {res}")
            hud.append_message("Thanatos", res)
            if (mode == "voice" or source == "voice") and not is_muted:
                state_manager.transition_to(State.SPEAKING)
                speak(res)
            state_manager.transition_to(State.IDLE)
            return

        # ----------------------------------------------------
        # 4. CHAT CONVERSATION & KNOWLEDGE HIERARCHY
        # ----------------------------------------------------
        state_manager.transition_to(State.THINKING)
        print("Thanatos: Thinking...", end="", flush=True)
        try:
            response = brain.respond(message)
        except Exception as e:  # noqa: BLE001
            state_manager.transition_to(State.ERROR)
            msg = f"Something went wrong: {e}"
            print(f"\rThanatos: {msg}" + " " * 20)
            hud.append_message("Thanatos", msg)
            state_manager.transition_to(State.IDLE)
            return

        # Erase "Thanatos: Thinking..." before printing response
        print("\r" + " " * 30 + "\r", end="", flush=True)
        print(f"Thanatos: {response.display_text}")
        hud.append_message("Thanatos", response.display_text)

        if (mode == "voice" or source == "voice") and not is_muted and response.speech_text:
            state_manager.transition_to(State.SPEAKING)
            speak(response.speech_text)

        state_manager.transition_to(State.IDLE)

    # Background thread for non-blocking console input
    def terminal_reader() -> None:
        while is_running:
            try:
                line = sys.stdin.readline()
                if not line:
                    time.sleep(0.1)
                    continue
                text = line.strip()
                if text:
                    event_queue.put({"type": "query", "text": text, "source": "terminal"})
            except Exception:  # noqa: BLE001
                break

    input_thread = threading.Thread(target=terminal_reader, daemon=True)
    input_thread.start()

    print("\n" + "=" * 55)
    print("THANATOS DESKTOP ASSISTANT ACTIVE")
    print(" - Press Ctrl+Space to summon / collapse Mini-Deck")
    print(" - Press F8 for Vision LeetCode & DSA Mentor")
    print(" - Press Ctrl+Shift+V for Clipboard Smart Fix")
    print(" - Say 'Browse <url>' or 'Search on browser for <query>'")
    print(" - Say 'Wake up', 'Hey Thanatos', or click [🎙️] for Voice")
    print(" - Say 'Go to sleep' or 'I am not talking to you' to rest")
    print("=" * 55 + "\n")

    # Main Reactive Event Loop
    while is_running:
        if mode == "voice":
            wake_detector.pause()
            clap_detector.pause()
            state_manager.transition_to(State.LISTENING)
            print("\r[🎙️ Listening hands-free... speak naturally or say 'Go to sleep']   ", end="", flush=True)

            audio = audio_input.record_vad(
                silence_duration=0.8,
                timeout=15.0,
                cancel_check=lambda: not event_queue.empty(),
            )

            # Check if interrupted by external event (e.g. typing or click or F8)
            if not event_queue.empty():
                state_manager.transition_to(State.IDLE)
                event = event_queue.get_nowait()
                if event.get("type") == "exit":
                    break
                elif event.get("type") == "vision_mentor":
                    process_vision_mentor(
                        query=event.get("query", ""),
                        mode=event.get("mode", "hint"),
                        source=event.get("source", "hotkey"),
                    )
                elif event.get("type") == "clipboard_fix":
                    process_clipboard_fix(source=event.get("source", "hotkey"))
                elif event.get("type") == "query":
                    process_user_message(event["text"], source=event.get("source", "hud"))
                continue

            if audio is None or len(audio) == 0:
                # 15s Inactivity Timeout -> Go to sleep
                print("\r[😴 Inactivity timeout: Thanatos is resting. Say 'Wake up' to wake]      \n", flush=True)
                hud.append_message("System", "😴 Went to sleep due to inactivity. Say 'Wake up' to wake.")
                play_chime("sleep")
                mode = "text"
                state_manager.transition_to(State.IDLE)
                wake_detector.resume()
                clap_detector.resume()
                continue

            # Speech detected: Transcribe
            state_manager.transition_to(State.TRANSCRIBING)
            print("\r[Transcribing speech...]                                ", end="", flush=True)
            message = transcriber.transcribe(audio)
            print("\r" + " " * 45 + "\r", end="", flush=True)

            if not message.strip():
                state_manager.transition_to(State.IDLE)
                continue

            state_manager.transition_to(State.IDLE)
            print(f"You (Voice): {message}")
            hud.append_message("You (Voice)", message)

            process_user_message(message, source="voice")
            if not is_running:
                break
            continue

        else:
            # Text / Standby Mode: Wait for incoming query, hotkey, or wake event
            try:
                event = event_queue.get(timeout=0.25)
            except queue.Empty:
                continue

            ev_type = event.get("type")
            if ev_type == "exit":
                break
            elif ev_type == "vision_mentor":
                process_vision_mentor(
                    query=event.get("query", ""),
                    mode=event.get("mode", "hint"),
                    source=event.get("source", "hotkey"),
                )
                continue
            elif ev_type == "clipboard_fix":
                process_clipboard_fix(source=event.get("source", "hotkey"))
                continue
            elif ev_type == "voice_wake":
                mode = "voice"
                play_chime("wake")
                wake_detector.pause()
                clap_detector.pause()
                print("\n[🎙️ Voice wake triggered! Listening hands-free...]")
                hud.append_message("System", "🎙️ Woken into Hands-Free Voice Mode!")
                continue
            elif ev_type == "query":
                process_user_message(event["text"], source=event.get("source", "text"))
                if not is_running:
                    break

    shutdown_ui()
    logger.info("Thanatos Shutdown Complete.")
    sys.exit(0)


if __name__ == "__main__":
    main()
