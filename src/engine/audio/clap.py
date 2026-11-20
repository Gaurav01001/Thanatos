from __future__ import annotations

import threading
import time
from collections.abc import Callable

import numpy as np
import sounddevice as sd

try:
    from engine.core.logging import get_logger
except ImportError:
    from src.engine.core.logging import get_logger

logger = get_logger("clap")


class ClapDetector:
    """
    Lightweight acoustic transient detector that monitors the microphone stream
    for a distinct double-clap gesture (e.g. 👏 👏) to trigger hands-free wake-up.

    Uses peak amplitude, crest factor (impulse ratio), and a strict temporal
    window (0.12s - 0.75s) to differentiate claps from typing or steady background speech.
    """

    def __init__(
        self,
        on_double_clap: Callable[[], None],
        threshold: float = 0.15,
        crest_factor_threshold: float = 2.8,
        min_gap: float = 0.10,
        max_gap: float = 0.85,
        samplerate: int = 16000,
        block_size: int = 512,
    ) -> None:
        self.on_double_clap = on_double_clap
        self.threshold = threshold
        self.crest_factor_threshold = crest_factor_threshold
        self.min_gap = min_gap
        self.max_gap = max_gap
        self.samplerate = samplerate
        self.block_size = block_size

        self._last_clap_time: float = 0.0
        self._cooldown_until: float = 0.0
        self._is_running: bool = False
        self._is_paused: bool = False
        self._stream: sd.InputStream | None = None
        self._lock = threading.Lock()

    @property
    def is_running(self) -> bool:
        return self._is_running

    @property
    def is_paused(self) -> bool:
        return self._is_paused

    def process_audio_chunk(self, chunk: np.ndarray, timestamp: float | None = None) -> bool:
        """
        Processes an audio chunk and evaluates whether a double-clap occurred.
        Returns True if a double-clap was completed on this chunk.
        Exposed publicly for deterministic unit tests.
        """
        if self._is_paused:
            return False

        now = timestamp if timestamp is not None else time.time()
        if now < self._cooldown_until:
            return False

        # Flatten if multi-channel
        data = chunk.flatten()
        if len(data) == 0:
            return False

        peak = float(np.max(np.abs(data)))
        rms = float(np.sqrt(np.mean(data**2)))
        crest = peak / (rms + 1e-6)

        # Clap candidate: High peak + sharp impulse crest factor
        if peak >= self.threshold and crest >= self.crest_factor_threshold:
            gap = now - self._last_clap_time
            if self.min_gap <= gap <= self.max_gap:
                logger.info("Double-clap detected (gap: %.3fs) -> Triggering wake!", gap)
                self._cooldown_until = now + 1.0  # 1s cooldown to prevent bounce
                self._last_clap_time = 0.0
                return True
            # First clap or too slow: start tracking from this peak
            logger.debug("First clap registered (peak: %.3f, crest: %.2f) at %.3fs", peak, crest, now)
            self._last_clap_time = now

        # Invalidate old single claps that exceeded the max gap
        if self._last_clap_time > 0 and (now - self._last_clap_time) > self.max_gap:
            self._last_clap_time = 0.0

        return False

    def _audio_callback(self, indata, frames, time_info, status) -> None:
        if self._is_paused or not self._is_running:
            return

        detected = self.process_audio_chunk(indata)
        if detected and self.on_double_clap:
            threading.Thread(target=self.on_double_clap, daemon=True).start()

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
                logger.info("ClapDetector listener active (threshold: %.2f)", self.threshold)
                return True
            except Exception as e:  # noqa: BLE001
                logger.warning("Could not start ClapDetector stream: %s", e)
                return False

    def pause(self) -> None:
        """Temporarily suspends clap detection (e.g. during TTS or active voice recording)."""
        self._is_paused = True

    def resume(self) -> None:
        """Resumes clap detection after audio playback or recording finishes."""
        with self._lock:
            if not self._is_paused:
                return
            self._last_clap_time = 0.0
            self._cooldown_until = time.time() + 0.3
            self._is_paused = False

    def stop(self) -> None:
        """Stops and closes the audio stream."""
        with self._lock:
            self._is_running = False
            if self._stream is not None:
                try:
                    self._stream.stop()
                    self._stream.close()
                except Exception:  # noqa: BLE001, S110
                    pass
                self._stream = None
            logger.info("ClapDetector stopped")
