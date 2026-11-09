from __future__ import annotations

import collections
import queue
import threading
import time
from collections.abc import Callable
from typing import Any

import numpy as np
import sounddevice as sd

try:
    from engine.audio.audio import is_wake_command
    from engine.core.logging import get_logger
except ImportError:
    from src.engine.audio.audio import is_wake_command
    from src.engine.core.logging import get_logger

logger = get_logger("wake")


class WakeWordDetector:
    """
    Continuous background spoken wake-word listener.
    Monitors microphone audio in standby mode for verbal cues like:
    "Wake up", "Hey Thanatos", "Wake up Thanatos", "Start listening".
    
    Uses near-zero CPU when idle, triggering light Whisper transcription
    only when human speech energy is detected.
    """

    def __init__(
        self,
        transcriber: Any,
        on_wake: Callable[[str], None],
        energy_threshold: float | None = None,
        samplerate: int = 16000,
        block_size: int = 512,
    ) -> None:
        self.transcriber = transcriber
        self.on_wake = on_wake
        self.energy_threshold = energy_threshold
        self.samplerate = samplerate
        self.block_size = block_size

        self._is_running: bool = False
        self._is_paused: bool = False
        self._cooldown_until: float = 0.0
        self._lock = threading.Lock()
        self._audio_queue: queue.Queue[np.ndarray] = queue.Queue()
        self._stream: sd.InputStream | None = None
        self._worker_thread: threading.Thread | None = None

    @property
    def is_running(self) -> bool:
        return self._is_running

    @property
    def is_paused(self) -> bool:
        return self._is_paused

    def _audio_callback(self, indata, frames, time_info, status) -> None:
        if not self._is_paused and self._is_running:
            self._audio_queue.put(indata.copy().flatten())

    def _worker_loop(self) -> None:
        """Background worker thread monitoring speech energy and transcribing wake phrases."""
        # 1. Calibrate initial ambient noise baseline (~300ms)
        calib_blocks: list[np.ndarray] = []
        t_calib = time.time() + 0.3
        while time.time() < t_calib and self._is_running:
            try:
                blk = self._audio_queue.get(timeout=0.05)
                calib_blocks.append(blk)
            except queue.Empty:
                continue

        if self.energy_threshold is None:
            if calib_blocks:
                amb_rms = float(np.mean([np.sqrt(np.mean(b**2)) for b in calib_blocks]))
                threshold = max(0.012, amb_rms * 2.2)
            else:
                threshold = 0.016
        else:
            threshold = self.energy_threshold

        logger.info("WakeWordDetector active (baseline threshold: %.4f)", threshold)

        pre_roll: collections.deque[np.ndarray] = collections.deque(maxlen=6)

        while self._is_running:
            if self._is_paused or time.time() < self._cooldown_until:
                # Flush queue while paused/cooling down
                try:
                    self._audio_queue.get(timeout=0.1)
                except queue.Empty:
                    pass
                continue

            try:
                chunk = self._audio_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            pre_roll.append(chunk)
            rms = float(np.sqrt(np.mean(chunk**2)))

            # Speech onset detected
            if rms >= threshold:
                collected = list(pre_roll)
                speech_blocks = 0
                silence_blocks = 0
                max_blocks = int(2.5 * self.samplerate / self.block_size)  # ~2.5s maximum snippet
                silence_limit = int(0.5 * self.samplerate / self.block_size)  # 500ms pause cutoff

                while self._is_running and not self._is_paused and speech_blocks < max_blocks:
                    try:
                        blk = self._audio_queue.get(timeout=0.1)
                    except queue.Empty:
                        break

                    collected.append(blk)
                    speech_blocks += 1
                    b_rms = float(np.sqrt(np.mean(blk**2)))
                    if b_rms < threshold * 0.7:
                        silence_blocks += 1
                        if silence_blocks >= silence_limit:
                            break
                    else:
                        silence_blocks = 0

                # Audio gathered for candidate wake word
                if len(collected) > 10 and self._is_running and not self._is_paused:
                    audio_arr = np.concatenate(collected).astype(np.float32)
                    try:
                        spoken_text = self.transcriber.transcribe(audio_arr).strip()
                    except Exception as e:
                        logger.debug("Wake phrase transcription error: %s", e)
                        spoken_text = ""

                    if spoken_text:
                        logger.debug("Standby heard: '%s'", spoken_text)

                    if is_wake_command(spoken_text):
                        logger.info("Wake word matched: '%s' -> Waking assistant!", spoken_text)
                        self._cooldown_until = time.time() + 2.0
                        if self.on_wake:
                            threading.Thread(target=self.on_wake, args=(spoken_text,), daemon=True).start()

    def start(self) -> bool:
        """Starts the low-overhead background microphone listener."""
        with self._lock:
            if self._is_running:
                return True
            try:
                self._stream = sd.InputStream(
                    samplerate=self.samplerate,
                    blocksize=self.block_size,
                    channels=1,
                    dtype="float32",
                    callback=self._audio_callback,
                )
                self._stream.start()
                self._is_running = True
                self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
                self._worker_thread.start()
                return True
            except Exception as e:
                logger.warning("Could not start WakeWordDetector stream: %s", e)
                return False

    def pause(self) -> None:
        """Suspends wake word detection (e.g. during active voice mode or TTS)."""
        self._is_paused = True

    def resume(self) -> None:
        """Resumes wake word detection when returning to standby mode."""
        with self._lock:
            self._cooldown_until = time.time() + 0.3
            self._is_paused = False

    def stop(self) -> None:
        """Stops and closes the audio stream and worker thread."""
        with self._lock:
            self._is_running = False
            if self._stream is not None:
                try:
                    self._stream.stop()
                    self._stream.close()
                except Exception:
                    pass
                self._stream = None
            logger.info("WakeWordDetector stopped")

