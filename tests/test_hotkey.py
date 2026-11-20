from __future__ import annotations

import sys
import time
from pathlib import Path

# Add project root and src to sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))
sys.path.insert(0, str(root_dir / "src"))

from engine.core.hotkey import HotkeyManager


def test_hotkey_config_loading():
    print("--- [TEST 1] Testing HotkeyManager Config Loading ---")
    manager = HotkeyManager()
    print(f"Loaded hotkey: {manager.hotkey_str}")
    assert manager.hotkey_str == "<ctrl>+<space>", f"Expected '<ctrl>+<space>', got {manager.hotkey_str}"
    print("[PASS] Hotkey correctly loaded from config.json.\n")


def test_hotkey_debounce_logic():
    print("--- [TEST 2] Testing Hotkey Debounce Guard ---")
    trigger_count = 0

    def on_press():
        nonlocal trigger_count
        trigger_count += 1

    manager = HotkeyManager(on_trigger=on_press)

    # First trigger should execute
    manager._handle_trigger()
    assert trigger_count == 1, "First trigger should succeed"

    # Rapid second trigger (50ms later) should be ignored by debounce
    time.sleep(0.05)
    manager._handle_trigger()
    assert trigger_count == 1, "Immediate re-trigger must be ignored by debounce"

    # Trigger after debounce interval (450ms) should execute
    time.sleep(0.45)
    manager._handle_trigger()
    assert trigger_count == 2, "Trigger after debounce interval should succeed"
    print("[PASS] Debounce logic correctly prevented rapid double-triggers.\n")


def test_hotkey_lifecycle():
    print("--- [TEST 3] Testing Hotkey Lifecycle (Start & Stop) ---")
    manager = HotkeyManager()
    started = manager.start()
    assert started is True, "Hotkey listener should start successfully"
    assert manager.is_alive is True, "Hotkey thread should be alive"

    manager.stop()
    assert manager.is_alive is False, "Hotkey listener should stop cleanly"
    print("[PASS] Hotkey listener thread starts and terminates cleanly.\n")


if __name__ == "__main__":
    test_hotkey_config_loading()
    test_hotkey_debounce_logic()
    test_hotkey_lifecycle()
    print("========================================")
    print("ALL STEP 2 HOTKEY TESTS PASSED!")
    print("========================================")
