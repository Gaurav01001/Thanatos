import os
import glob
import difflib

class Executor:

    def __init__(self):
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