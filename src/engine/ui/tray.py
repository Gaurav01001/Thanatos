from __future__ import annotations

import ctypes
import logging
import threading
from collections.abc import Callable
from typing import TYPE_CHECKING, ClassVar

import pystray
from PIL import Image, ImageDraw

if TYPE_CHECKING:
    from engine.core.state import State

logger = logging.getLogger(__name__)


def create_tray_icon_image(color: str = "#7aa2f7", size: int = 64) -> Image.Image:
    """Generates a sleek, anti-aliased circular tray icon in memory."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Outer dark Tokyo Night circular border
    draw.ellipse([4, 4, size - 4, size - 4], fill="#1a1b26", outline="#24283b", width=3)
    # Inner glowing indicator circle
    draw.ellipse([18, 18, size - 18, size - 18], fill=color)

    return img


class SystemTrayApp:
    """Manages the Windows taskbar system tray icon and background controls."""

    STATE_COLORS: ClassVar[dict[str, str]] = {
        "idle": "#7aa2f7",       # Tokyo Night Soft Cyan
        "listening": "#7dcfff",  # Electric Blue
        "thinking": "#e0af68",   # Warm Amber
        "speaking": "#9ece6a",   # Bright Mint Green
        "executing": "#bb9af7",  # Purple
        "error": "#f7768e",      # Coral Red
    }

    def __init__(
        self,
        on_mute_toggle: Callable[[], bool] | None = None,
        on_quit: Callable[[], None] | None = None,
    ) -> None:
        self.on_mute_toggle = on_mute_toggle
        self.on_quit = on_quit
        self.is_muted: bool = False
        self.current_state_name: str = "idle"
        self._terminal_visible: bool = True
        self._icon: pystray.Icon | None = None
        self._thread: threading.Thread | None = None

    def _get_console_window(self) -> int:
        """Retrieves the Windows HWND handle of the current terminal window."""
        try:
            return ctypes.windll.kernel32.GetConsoleWindow()
        except Exception:  # noqa: BLE001
            return 0

    def toggle_terminal(self) -> None:
        """Shows or hides the PowerShell terminal window."""
        hwnd = self._get_console_window()
        if hwnd == 0:
            return

        if self._terminal_visible:
            # SW_HIDE = 0
            ctypes.windll.user32.ShowWindow(hwnd, 0)
            self._terminal_visible = False
            logger.info("Terminal window hidden to background")
        else:
            # SW_SHOW = 5
            ctypes.windll.user32.ShowWindow(hwnd, 5)
            ctypes.windll.user32.SetForegroundWindow(hwnd)
            self._terminal_visible = True
            logger.info("Terminal window restored to foreground")

    def _handle_mute_toggle(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        """Toggles audio mute state."""
        if self.on_mute_toggle:
            self.is_muted = self.on_mute_toggle()
        else:
            self.is_muted = not self.is_muted
        self.update_menu()

    def _handle_terminal_toggle(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        """Toggles terminal window visibility."""
        self.toggle_terminal()
        self.update_menu()

    def _handle_exit(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        """Clean shutdown from tray."""
        self.stop()
        if self.on_quit:
            self.on_quit()

    def _build_menu(self) -> pystray.Menu:
        """Constructs the right-click context menu."""
        status_label = f"Status: {self.current_state_name.capitalize()}"
        mute_label = "Unmute Audio" if self.is_muted else "Mute Audio"
        terminal_label = "Hide Terminal" if self._terminal_visible else "Show Terminal"

        return pystray.Menu(
            pystray.MenuItem(status_label, lambda icon, item: None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(mute_label, self._handle_mute_toggle),
            pystray.MenuItem(terminal_label, self._handle_terminal_toggle),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Exit Thanatos", self._handle_exit),
        )

    def on_state_change(self, old_state: State, new_state: State) -> None:
        """Callback to update tray tooltip and icon color on StateManager transitions."""
        self.current_state_name = new_state.value
        color = self.STATE_COLORS.get(new_state.value, "#7aa2f7")

        if self._icon:
            self._icon.title = f"Thanatos: {self.current_state_name.capitalize()}"
            self._icon.icon = create_tray_icon_image(color)
            self.update_menu()

    def update_menu(self) -> None:
        """Refreshes the right-click menu items."""
        if self._icon:
            self._icon.menu = self._build_menu()

    def start(self) -> None:
        """Starts the system tray icon in a dedicated daemon thread."""
        if self._icon is not None:
            return

        icon_image = create_tray_icon_image()
        self._icon = pystray.Icon(
            name="Thanatos",
            icon=icon_image,
            title="Thanatos: Idle",
            menu=self._build_menu(),
        )

        self._thread = threading.Thread(target=self._icon.run, daemon=True)
        self._thread.start()
        logger.info("System Tray icon active in taskbar")

    def stop(self) -> None:
        """Stops and removes the tray icon."""
        if self._icon:
            self._icon.stop()
            self._icon = None
            logger.info("System Tray icon stopped")
