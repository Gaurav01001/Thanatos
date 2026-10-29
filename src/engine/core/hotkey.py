from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from pathlib import Path

from pynput import keyboard

logger = logging.getLogger(__name__)


class HotkeyManager:
    """Manages system-wide global hotkeys using pynput.
    
    Runs on a lightweight, event-driven background thread consuming ~0% CPU.
    """

    def __init__(
        self,
        hotkey: str | None = None,
        on_trigger: Callable[[], None] | None = None,
        config_path: Path | None = None,
    ) -> None:
        self.config_path = config_path or (Path(__file__).resolve().parents[3] / "config.json")
        self.hotkey_str = hotkey or self._load_hotkey_from_config()
        self.on_trigger = on_trigger
        self._listener: keyboard.GlobalHotKeys | None = None
        self._last_trigger_time: float = 0.0
        self._debounce_interval: float = 0.4  # 400ms debounce guard

    def _load_hotkey_from_config(self) -> str:
        """Reads hotkey string from config.json if present, otherwise default to <ctrl>+<space>."""
        default_hotkey = "<ctrl>+<space>"
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("hotkey", default_hotkey)
            except Exception as e:  # noqa: BLE001
                logger.warning("Failed to load hotkey from config: %s", e)
        return default_hotkey

    def _handle_trigger(self) -> None:
        """Debounced callback invoked when the global hotkey is pressed."""
        now = time.time()
        if now - self._last_trigger_time < self._debounce_interval:
            return

        self._last_trigger_time = now
        logger.info("Global hotkey triggered: %s", self.hotkey_str)

        if self.on_trigger:
            try:
                self.on_trigger()
            except Exception as e:  # noqa: BLE001
                logger.error("Error executing hotkey callback: %s", e)

    def start(self) -> bool:
        """Starts the global hotkey listener thread."""
        if self._listener is not None:
            return True

        try:
            hotkey_mapping = {self.hotkey_str: self._handle_trigger}
            self._listener = keyboard.GlobalHotKeys(hotkey_mapping)
            self._listener.daemon = True
            self._listener.start()
            logger.info("Global hotkey listener active on [%s]", self.hotkey_str)
            return True
        except Exception as e:  # noqa: BLE001
            logger.error("Failed to register global hotkey [%s]: %s", self.hotkey_str, e)
            self._listener = None
            return False

    def stop(self) -> None:
        """Stops the global hotkey listener cleanly."""
        if self._listener:
            try:
                self._listener.stop()
            except Exception:  # noqa: BLE001, S110
                pass
            self._listener = None
            logger.info("Global hotkey listener stopped")

    @property
    def is_alive(self) -> bool:
        """Checks if the listener thread is active."""
        return self._listener is not None and self._listener.is_alive()
