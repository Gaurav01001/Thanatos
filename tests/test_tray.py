from __future__ import annotations

import sys
from pathlib import Path

# Add project root and src to sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))
sys.path.insert(0, str(root_dir / "src"))

from engine.core.state import State
from engine.ui.tray import SystemTrayApp, create_tray_icon_image


def test_tray_icon_drawing():
    print("--- [TEST 1] Testing Dynamic Tray Icon Generation ---")
    img = create_tray_icon_image("#7aa2f7", size=64)
    assert img.size == (64, 64), f"Expected 64x64 icon, got {img.size}"
    assert img.mode == "RGBA", f"Expected RGBA mode, got {img.mode}"
    print("[PASS] Anti-aliased dynamic icon drawn successfully in memory.\n")


def test_tray_menu_structure():
    print("--- [TEST 2] Testing SystemTrayApp Menu Structure ---")
    tray = SystemTrayApp()
    menu = tray._build_menu()
    items = [item.text for item in menu.items if hasattr(item, "text")]
    print(f"Generated menu items: {items}")

    assert any("Status: Idle" in item for item in items)
    assert any("Mute Audio" in item for item in items)
    assert any("Hide Terminal" in item for item in items)
    assert any("Exit Thanatos" in item for item in items)
    print("[PASS] System Tray menu generated with all status and control items.\n")


def test_tray_state_synchronization():
    print("--- [TEST 3] Testing State Transition Synchronization ---")
    tray = SystemTrayApp()

    # Simulate transition to THINKING
    tray.on_state_change(State.IDLE, State.THINKING)
    assert tray.current_state_name == "thinking"
    menu = tray._build_menu()
    items = [item.text for item in menu.items if hasattr(item, "text")]
    assert any("Status: Thinking" in item for item in items)
    print(f"Updated status: {items[0]}")

    # Simulate transition to SPEAKING
    tray.on_state_change(State.THINKING, State.SPEAKING)
    assert tray.current_state_name == "speaking"
    menu = tray._build_menu()
    items = [item.text for item in menu.items if hasattr(item, "text")]
    assert any("Status: Speaking" in item for item in items)
    print(f"Updated status: {items[0]}")
    print("[PASS] Tray menu dynamically updates state synchronously.\n")


if __name__ == "__main__":
    test_tray_icon_drawing()
    test_tray_menu_structure()
    test_tray_state_synchronization()
    print("========================================")
    print("ALL STEP 3 SYSTEM TRAY TESTS PASSED!")
    print("========================================")
