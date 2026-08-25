import os
import difflib
import urllib.parse
import time
import ctypes
from pynput.keyboard import Controller, Key

class Executor:

    def __init__(self):
        # Index all installed apps on startup
        self.app_index = self._scan_installed_apps()

    def _scan_installed_apps(self) -> dict:
        """Scans Windows Start Menu directories to index all installed apps."""
        apps = {}
        start_menu_paths = [
            r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs",
            os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs")
        ]

        for base_path in start_menu_paths:
            if os.path.exists(base_path):
                for root, _, files in os.walk(base_path):
                    for file in files:
                        if file.endswith((".lnk", ".url", ".exe")):
                            app_name = os.path.splitext(file)[0].lower()
                            full_path = os.path.join(root, file)
                            apps[app_name] = full_path
        return apps

    def open_application(self, app_name: str) -> bool:
        """Finds and launches any installed app using fuzzy matching."""
        app_clean = app_name.lower().strip()

        # 1. Check direct or fuzzy match in indexed installed apps
        matches = difflib.get_close_matches(app_clean, self.app_index.keys(), n=1, cutoff=0.5)
        if matches:
            target_path = self.app_index[matches[0]]
            try:
                os.startfile(target_path)
                return True
            except Exception:
                pass

        # 2. Fallback to Windows shell command (calc, notepad, explorer, etc.)
        try:
            os.startfile(app_clean)
            return True
        except Exception:
            return False

    def open_file(self, filename: str, folder_hint: str = None) -> bool:
        """Searches user directories (Desktop, Downloads, Documents, etc.) and opens the file."""
        user_home = os.path.expanduser("~")
        search_dirs = [
            os.path.join(user_home, "Desktop"),
            os.path.join(user_home, "Downloads"),
            os.path.join(user_home, "Documents"),
            os.path.join(user_home, "Videos"),
            os.path.join(user_home, "Music"),
            os.path.join(user_home, "Pictures"),
        ]

        # If a specific folder hint is given (e.g. "Downloads")
        if folder_hint:
            hint_path = os.path.join(user_home, folder_hint.strip())
            if os.path.exists(hint_path):
                search_dirs.insert(0, hint_path)

        for base_dir in search_dirs:
            if os.path.exists(base_dir):
                for root, _, files in os.walk(base_dir):
                    matches = difflib.get_close_matches(filename.lower(), [f.lower() for f in files], n=1, cutoff=0.5)
                    if matches:
                        # Find the actual file with original casing
                        for f in files:
                            if f.lower() == matches[0]:
                                full_path = os.path.join(root, f)
                                os.startfile(full_path)
                                return True
        return False

    def play_spotify(self, query: str) -> bool:
        """Opens Spotify, focuses the window, and triggers playback for the top result."""
        if not query:
            return False

        clean_query = query.strip()
        encoded = urllib.parse.quote(clean_query)
        try:
            # 1. Opens Spotify search URI directly on Windows
            os.startfile(f"spotify:search:{encoded}")
            time.sleep(2.0)

            # 2. Bring Spotify window to the foreground so it receives keystrokes
            user32 = ctypes.windll.user32
            def enum_cb(hwnd, extra):
                if user32.IsWindowVisible(hwnd):
                    length = user32.GetWindowTextLengthW(hwnd)
                    buff = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buff, length + 1)
                    if "spotify" in buff.value.lower():
                        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                        user32.SetForegroundWindow(hwnd)
                return True

            WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
            user32.EnumWindows(WNDENUMPROC(enum_cb), 0)
            time.sleep(0.5)

            # 3. Navigate to top track and play
            keyboard = Controller()
            keyboard.press(Key.tab)
            keyboard.release(Key.tab)
            time.sleep(0.3)
            keyboard.press(Key.down)
            keyboard.release(Key.down)
            time.sleep(0.2)
            keyboard.press(Key.enter)
            keyboard.release(Key.enter)
            time.sleep(0.2)
            keyboard.press(Key.enter)
            keyboard.release(Key.enter)
            return True
        except Exception:
            return False


# "You should open Notepad"
#           ↓
#         Brain
#           ↓
# {"action": "open_application",
#  "target": "notepad"}
#           ↓
#         main.py
#           ↓
# Does action == "open_application"?
#           ↓ yes
#       EXECUTING
#           ↓
#        Executor
#           ↓
#     open_application()
#           ↓
#        Notepad