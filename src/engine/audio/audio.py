from __future__ import annotations

import collections
import queue
import re
import time
from collections.abc import Callable

import numpy as np
import sounddevice as sd
from pynput import keyboard

try:
    from engine.core.logging import get_logger
except ImportError:
    from src.engine.core.logging import get_logger

logger = get_logger("audio")


def is_sleep_command(text: str) -> bool:
    """
    Determines whether a spoken or typed message is a sleep / stand-down directive.
    Differentiates conversational commands ("go to sleep", "I'm not talking to you")
    from general queries ("How do I sleep better?").
    """
    if not text:
        return False

    cleaned = re.sub(r"[^\w\s]", "", text.lower()).strip()
    if cleaned in ("sleep", "shutup", "quiet", "stand down", "standby"):
        return True

    phrases = [
        "go to sleep",
        "sleep now",
        "stop listening",
        "im not talking to you",
        "i am not talking to you",
        "not talking to you",
        "shut up",
        "thats all",
        "that is all",
        "never mind",
        "nevermind",
        "be quiet",
        "stand down",
    ]
    return any(p in cleaned for p in phrases)


def is_wake_command(text: str) -> bool:
    """
    Determines whether a spoken or typed message is a wake-up directive
    (e.g. "wake up", "wake up thanatos", "hey thanatos", "are you there", "start listening").
    """
    if not text:
        return False

    cleaned = re.sub(r"[^\w\s]", "", text.lower()).strip()

    exact_matches = {
        "wake", "wake up", "wakeup", "wake up thanatos", "wakeup thanatos",
        "hey thanatos", "hi thanatos", "thanatos", "start listening",
        "listen", "are you awake", "are you there", "wake up jarvis",
        "jarvis", "hello thanatos", "thanatos wake up"
    }
    if cleaned in exact_matches:
        return True

    wake_phrases = [
        "wake up",
        "wakeup",
        "hey thanatos",
        "hi thanatos",
        "wake up thanatos",
        "start listening",
        "are you awake",
        "are you there",
        "thanatos wake up",
    ]
    for phrase in wake_phrases:
        if phrase in cleaned:
            return True

    match = re.match(
        r"^(?:please\s+|can you\s+|could you\s+)?(?:wake\s*up|wake|listen|start\s*listening)\s+(?:thanatos|assistant|jarvis)?$",
        cleaned,
    )
    return bool(match)


def is_exit_command(text: str) -> bool:
    """
    Determines whether a spoken or typed message is an exit/close/shutdown directive
    for the AI assistant (e.g. "exit", "quit", "close assistant", "shut down thanatos").
    """
    if not text:
        return False

    cleaned = re.sub(r"[^\w\s]", "", text.lower()).strip()

    exact_matches = {
        "exit", "quit", "bye", "goodbye", "terminate", "close",
        "shutdown", "stop", "poweroff"
    }
    if cleaned in exact_matches:
        return True

    exit_phrases = [
        "close assistant",
        "close the assistant",
        "close the ai assistant",
        "close ai assistant",
        "close thanatos",
        "exit assistant",
        "exit the assistant",
        "exit thanatos",
        "quit assistant",
        "quit thanatos",
        "shut down assistant",
        "shutdown assistant",
        "shut down the assistant",
        "shutdown the assistant",
        "shut down thanatos",
        "shutdown thanatos",
        "turn off assistant",
        "turn off the assistant",
        "turn off thanatos",
        "terminate assistant",
        "terminate the assistant",
        "terminate session",
        "terminate thanatos",
        "stop assistant",
        "kill assistant",
        "kill thanatos",
        "goodbye thanatos",
        "bye thanatos",
        "close the application",
        "close application",
        "close program",
        "exit program",
        "quit program",
    ]
    for phrase in exit_phrases:
        if phrase in cleaned:
            return True

    match = re.match(
        r"^(?:please\s+|can you\s+|could you\s+)?(?:exit|quit|close|shut\s*down|terminate|turn\s*off)\s+(?:the\s+)?(?:ai\s+)?(?:assistant|thanatos|app|program|session)$",
        cleaned,
    )
    return bool(match)


def play_chime(kind: str = "wake", samplerate: int = 24000) -> None:
    """
    Plays a brief, non-intrusive synthesized audio cue:
    - 'wake': ascending dual-tone chime (G5 -> C6)
    - 'sleep': descending dual-tone chime (A5 -> A4)
    """
    try:
        duration = 0.20
        t = np.linspace(0, duration, int(samplerate * duration), endpoint=False)
        half = len(t) // 2
        if kind == "wake":
            f1, f2 = 784.0, 1046.5
        else:
            f1, f2 = 880.0, 440.0

        t1 = t[:half]
        t2 = t[half:]
        env1 = np.exp(-14 * np.linspace(0, duration / 2, half))
        env2 = np.exp(-9 * np.linspace(0, duration / 2, len(t2)))

        tone1 = np.sin(2 * np.pi * f1 * t1) * env1
        tone2 = np.sin(2 * np.pi * f2 * t2) * env2
        chime = (np.concatenate([tone1, tone2]) * 0.15).astype(np.float32)
        sd.play(chime, samplerate=samplerate)
    except Exception as e:  # noqa: BLE001
        logger.debug("Could not play audio chime: %s", e)


class AudioInput:
    """
    Manages microphone input capture with support for both:
    1. Spacebar push-to-talk (manual mode).
    2. Hands-Free Voice Activity Detection (VAD) with silence cutoff and pre-roll.
    """

    def __init__(self, samplerate: int = 16000):
        try:
            self.device = sd.query_devices(kind="input")
        except Exception as e:  # noqa: BLE001
            logger.warning("No default input device found: %s", e)
            self.device = None
        self.samplerate = samplerate

    def record(self) -> np.ndarray | None:
        """
        Manual Push-to-Talk: Hold Space to record, release to transcribe.
        Pressing Esc cancels recording.
        """
        print("\r[Hold Space to speak, Esc to cancel]", end="", flush=True)
        frames: list[np.ndarray] = []
        is_recording = False
        cancelled = False

        def audio_callback(indata, frame_count, time_info, status):
            if is_recording:
                frames.append(indata.copy())

        stream = sd.InputStream(
            samplerate=self.samplerate,
            channels=1,
            dtype="float32",
            callback=audio_callback,
        )

        def on_press(key):
            nonlocal is_recording, cancelled
            if key == keyboard.Key.space and not is_recording:
                is_recording = True
                print("\r[Recording... release Space to send]   ", end="", flush=True)
            elif key == keyboard.Key.esc:
                cancelled = True
                return False

        def on_release(key):
            nonlocal is_recording, cancelled
            if key == keyboard.Key.space and is_recording:
                is_recording = False
                print("\r[Transcribing...]                      ", end="", flush=True)
                return False  # Stop listener
            elif key == keyboard.Key.esc:
                cancelled = True
                return False

        with stream, keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
            listener.join()

        # Clear the status line
        print("\r" + " " * 45 + "\r", end="", flush=True)

        if cancelled:
            return None

        if frames:
            audio = np.concatenate(frames, axis=0)
            return audio.flatten().astype(np.float32)
        return np.array([], dtype=np.float32)

    def record_vad(
        self,
        silence_duration: float = 0.8,
        timeout: float = 15.0,
        energy_threshold: float | None = None,
        cancel_check: Callable[[], bool] | None = None,
        max_duration: float = 30.0,
        block_size: int = 512,
    ) -> np.ndarray | None:
        """
        Hands-Free Voice Activity Detection (VAD) recording:
        1. Dynamically estimates ambient room noise for initial baseline.
        2. Maintains a 250ms rolling pre-roll buffer to prevent clipped starting words.
        3. Waits up to `timeout` seconds for user to begin speaking.
        4. Once speaking begins, continues recording until speech pauses for `silence_duration` seconds.
        5. Returns float32 numpy audio, or None if timed out or cancelled.
        """
        audio_queue: queue.Queue[np.ndarray] = queue.Queue()

        def audio_callback(indata, frames, time_info, status):
            audio_queue.put(indata.copy().flatten())

        try:
            stream = sd.InputStream(
                samplerate=self.samplerate,
                channels=1,
                blocksize=block_size,
                dtype="float32",
                callback=audio_callback,
            )
        except Exception as e:  # noqa: BLE001
            logger.error("Failed to open audio input stream for VAD: %s", e)
            return None

        # 1. Ambient calibration (first ~8 blocks / ~256ms)
        pre_roll: collections.deque[np.ndarray] = collections.deque(maxlen=8)
        calibration_blocks: list[np.ndarray] = []

        start_time = time.time()
        with stream:
            # Calibrate baseline ambient energy
            calib_end = time.time() + 0.25
            while time.time() < calib_end:
                if cancel_check and cancel_check():
                    return None
                try:
                    blk = audio_queue.get(timeout=0.05)
                    calibration_blocks.append(blk)
                    pre_roll.append(blk)
                except queue.Empty:
                    continue

            if energy_threshold is None:
                if calibration_blocks:
                    amb_rms = float(np.mean([np.sqrt(np.mean(b**2)) for b in calibration_blocks]))
                    threshold = max(0.012, amb_rms * 2.2)
                else:
                    threshold = 0.015
            else:
                threshold = energy_threshold

            # 2. Wait for speech to trigger
            speech_started = False
            recorded_frames: list[np.ndarray] = []

            while not speech_started:
                if cancel_check and cancel_check():
                    return None
                if (time.time() - start_time) > timeout:
                    # Inactivity timeout (e.g. 15s of silence)
                    return None

                try:
                    blk = audio_queue.get(timeout=0.1)
                except queue.Empty:
                    continue

                pre_roll.append(blk)
                rms = float(np.sqrt(np.mean(blk**2)))

                if rms >= threshold:
                    speech_started = True
                    # Prepend pre-roll buffer so the first phoneme is not clipped
                    recorded_frames.extend(list(pre_roll))

            # 3. Speech in progress: Record until silence duration is met
            silence_samples = 0
            silence_target = int(silence_duration * self.samplerate)
            max_samples = int(max_duration * self.samplerate)
            total_samples = sum(len(f) for f in recorded_frames)

            while True:
                if cancel_check and cancel_check():
                    return None

                try:
                    blk = audio_queue.get(timeout=0.1)
                except queue.Empty:
                    continue

                recorded_frames.append(blk)
                total_samples += len(blk)

                rms = float(np.sqrt(np.mean(blk**2)))
                if rms >= threshold * 0.7:
                    silence_samples = 0  # Still speaking
                else:
                    silence_samples += len(blk)

                # Silence pause reached?
                if silence_samples >= silence_target:
                    break

                # Safety maximum duration reached?
                if total_samples >= max_samples:
                    break

        if recorded_frames:
            return np.concatenate(recorded_frames, axis=0).astype(np.float32)
        return np.array([], dtype=np.float32)