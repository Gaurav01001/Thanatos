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
    
    Supports multiple simultaneous shortcuts (e.g. HUD toggle and Vision Mentor)
    with per-key debounce intervals and zero-overhead background listener thread.
    """

    def __init__(
        self,
        hotkey: str | None = None,
        on_trigger: Callable[[], None] | None = None,
        vision_hotkey: str | None = None,
        on_vision_trigger: Callable[[], None] | None = None,
        config_path: Path | None = None,
    ) -> None:
        self.config_path = config_path or (Path(__file__).resolve().parents[3] / "config.json")
        
        # Load shortcuts from config.json or use defaults
        config_data = self._load_config()
        self.hud_hotkey_str = hotkey or config_data.get("hotkey", "<ctrl>+<space>")
        self.hotkey_str = self.hud_hotkey_str  # Backwards compatibility alias
        self.vision_hotkey_str = vision_hotkey or config_data.get("vision_hotkey", "<f8>")
        
        # Callbacks
        self.on_hud_trigger = on_trigger
        self.on_vision_trigger = on_vision_trigger
        
        # Per-hotkey debounce tracking (400ms guard)
        self._last_triggers: dict[str, float] = {}
        self._debounce_interval: float = 0.4
        
        self._listener: keyboard.GlobalHotKeys | None = None

    def _load_config(self) -> dict:
        """Reads configuration file safely."""
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning("Failed to load config: %s", e)
        return {}

    def _debounce(self, key_name: str) -> bool:
        """Returns True if the hotkey event is within the debounce cooldown."""
        now = time.time()
        last_time = self._last_triggers.get(key_name, 0.0)
        if now - last_time < self._debounce_interval:
            return True
        self._last_triggers[key_name] = now
        return False

    def _handle_hud_trigger(self) -> None:
        """Debounced callback for HUD Mini-Deck."""
        if self._debounce("hud"):
            return
        logger.info("HUD hotkey triggered: %s", self.hud_hotkey_str)
        if self.on_hud_trigger:
            try:
                self.on_hud_trigger()
            except Exception as e:
                logger.error("Error executing HUD hotkey callback: %s", e)

    def _handle_trigger(self) -> None:
        """Backwards compatibility alias for _handle_hud_trigger."""
        self._handle_hud_trigger()

    def _handle_vision_trigger(self) -> None:
        """Debounced callback for Vision DSA Mentor."""
        if self._debounce("vision"):
            return
        logger.info("Vision mentor hotkey triggered: %s", self.vision_hotkey_str)
        if self.on_vision_trigger:
            try:
                self.on_vision_trigger()
            except Exception as e:
                logger.error("Error executing vision hotkey callback: %s", e)

    def start(self) -> bool:
        """Starts the multi-hotkey listener thread."""
        if self._listener is not None:
            return True

        mapping = {}
        if self.on_hud_trigger:
            mapping[self.hud_hotkey_str] = self._handle_hud_trigger
        if self.on_vision_trigger:
            mapping[self.vision_hotkey_str] = self._handle_vision_trigger

        # If no callbacks were explicitly registered, register HUD default
        if not mapping and self.hud_hotkey_str:
            mapping[self.hud_hotkey_str] = self._handle_hud_trigger

        try:
            self._listener = keyboard.GlobalHotKeys(mapping)
            self._listener.daemon = True
            self._listener.start()
            logger.info("Global hotkeys active: %s", list(mapping.keys()))
            return True
        except Exception as e:
            logger.error("Failed to register global hotkeys: %s", e)
            self._listener = None
            return False

    def stop(self) -> None:
        """Stops the global hotkey listener cleanly."""
        if self._listener:
            try:
                self._listener.stop()
            except Exception:
                pass
            self._listener = None
            logger.info("Global hotkey listener stopped")

    @property
    def is_alive(self) -> bool:
        return self._listener is not None and self._listener.is_alive()