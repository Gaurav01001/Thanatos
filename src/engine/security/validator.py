import os
from typing import Tuple, Optional


class SecurityValidator:
    """
    Validates actions, application names, file names, and file paths
    before they are passed to the Executor.
    """

    # Characters that should never appear in application/file input.
    DANGEROUS_CHARACTERS = {
        ";", "&", "&&", "||", "|", "`", "$", "%", ">", "<", "^", "\n", "\r"
    }

    # Commands that should never be executed by Thanatos.
    BLOCKED_COMMANDS = {
        "format",
        "diskpart",
        "reg",
        "regedit",
        "bcdedit",
        "vssadmin",
        "cipher",
        "attrib",
        "takeown",
        "icacls",
        "netsh",
        "net",
        "taskkill",
        "stop-process",
        "remove-item",
        "del",
        "rmdir",
        "rd",
    }

    # System locations Thanatos should never access.
    PROTECTED_DIRECTORIES = [
        r"C:\Windows",
        r"C:\Windows\System32",
        r"C:\Windows\SysWOW64",
        r"C:\Boot",
        r"C:\Recovery",
        r"C:\ProgramData\Microsoft\Windows Defender",
    ]

    # Executable/script types we don't want to launch directly.
    BLOCKED_EXTENSIONS = {
        ".bat",
        ".cmd",
        ".vbs",
        ".ps1",
        ".reg",
        ".scr",
        ".pif",
    }

    # Actions that are explicitly allowed without confirmation.
    SAFE_ACTIONS = {
        "open_application",
        "open_file",
        "play_music",
        "chat",
        "take_screenshot",
        "analyze_image",
        "analyze_screen",
        "look_at_screen",
    }

    # Actions that should require user confirmation.
    CONFIRM_ACTIONS = {
        "delete_file",
        "delete_folder",
        "shutdown",
        "restart",
        "close_application",
    }

    def _contains_dangerous_characters(self, value: str) -> Optional[str]:
        """
        Checks for shell/control characters.
        Returns an error message if something dangerous is found.
        """

        for character in self.DANGEROUS_CHARACTERS:
            if character in value:
                return (
                    f"Security Alert: Dangerous character "
                    f"'{character}' detected."
                )

        return None

    def _is_protected_path(self, path: str) -> Optional[str]:
        """
        Checks whether a path is inside a protected Windows directory.
        """

        try:
            normalized_path = os.path.normcase(
                os.path.abspath(
                    os.path.expanduser(path)
                )
            )

            for protected_directory in self.PROTECTED_DIRECTORIES:
                normalized_protected = os.path.normcase(
                    os.path.abspath(protected_directory)
                )

                try:
                    common_path = os.path.commonpath(
                        [normalized_path, normalized_protected]
                    )
                except ValueError:
                    continue

                if common_path == normalized_protected:
                    return (
                        f"Security Alert: Access to protected "
                        f"system directory '{protected_directory}' is denied."
                    )

        except (OSError, ValueError):
            return "Invalid or unsafe path."

        return None

    def validate_application(
        self,
        app_name: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Validates an application name before launching it.

        Returns:
            (True, None) if safe.
            (False, reason) if blocked.
        """

        if not isinstance(app_name, str) or not app_name.strip():
            return False, "Application name cannot be empty."

        clean_name = app_name.strip().lower()

        # Check dangerous characters.
        reason = self._contains_dangerous_characters(clean_name)

        if reason:
            return False, reason

        # Check blocked commands.
        tokens = clean_name.split()

        if tokens and tokens[0] in self.BLOCKED_COMMANDS:
            return (
                False,
                f"Security Alert: Command '{tokens[0]}' is blocked."
            )

        # Check dangerous executable extensions.
        _, extension = os.path.splitext(clean_name)

        if extension in self.BLOCKED_EXTENSIONS:
            return (
                False,
                f"Security Alert: Executing '{extension}' files is blocked."
            )

        return True, None

    def validate_file_name(
        self,
        file_name: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Validates a file name without treating it as an application.
        """

        if not isinstance(file_name, str) or not file_name.strip():
            return False, "File name cannot be empty."

        clean_name = file_name.strip()

        # Prevent shell/control injection.
        reason = self._contains_dangerous_characters(clean_name)

        if reason:
            return False, reason

        # Prevent path traversal.
        if ".." in clean_name:
            return False, "Security Alert: Path traversal is not allowed."

        # A file target should not contain path separators.
        if "\\" in clean_name or "/" in clean_name:
            return False, "File target must be a file name, not a path."

        return True, None

    def validate_file_path(
        self,
        file_path: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Validates a complete file or folder path.
        """

        if not isinstance(file_path, str) or not file_path.strip():
            return False, "File path cannot be empty."

        clean_path = file_path.strip()

        # Check dangerous shell/control characters.
        reason = self._contains_dangerous_characters(clean_path)

        if reason:
            return False, reason

        # Prevent path traversal.
        if ".." in clean_path:
            return False, "Security Alert: Path traversal is not allowed."

        # Check protected Windows directories.
        reason = self._is_protected_path(clean_path)

        if reason:
            return False, reason

        return True, None

    def validate_intent(
        self,
        intent: dict
    ) -> Tuple[str, Optional[str]]:
        """
        Validates a complete structured intent.

        Returns:

            ("SAFE", None)
            ("CONFIRM", reason)
            ("BLOCKED", reason)
        """
        
        if not isinstance(intent, dict):
            return "BLOCKED", "Invalid intent structure."

        action = intent.get("action")
        target = intent.get("target")
        folder = intent.get("folder")

        if not isinstance(action, str):
            return "BLOCKED", "Invalid action."

        action = action.strip().lower()

        # Screenshot action is always safe and needs no target.
        if action in ("take_screenshot", "analyze_image", "analyze_screen", "look_at_screen"):
            return "SAFE", None
 
        # Unknown actions fail closed.
        if (
            action not in self.SAFE_ACTIONS
            and action not in self.CONFIRM_ACTIONS
        ):
            return "BLOCKED", f"Unknown action '{action}'."

        # Actions requiring confirmation.
        if action in self.CONFIRM_ACTIONS:
            return (
                "CONFIRM",
                f"Action '{action}' requires user confirmation."
            )

        # Normal conversation needs no target.
        if action == "chat":
            return "SAFE", None

        # All other supported actions need a target.
        if not isinstance(target, str) or not target.strip():
            return "BLOCKED", "Action requires a target."

        # Application validation.
        if action == "open_application":
            safe, reason = self.validate_application(target)
            if not safe:
                return "BLOCKED", reason
            return "SAFE", None

        # File validation.
        if action == "open_file":
            safe, reason = self.validate_file_name(target)

            if not safe:
                return "BLOCKED", reason

            if folder:
                safe, reason = self.validate_file_path(folder)

                if not safe:
                    return "BLOCKED", reason

            return "SAFE", None

        # Music target validation.
        if action == "play_music":
            reason = self._contains_dangerous_characters(target.strip())

            if reason:
                return "BLOCKED", reason

            return "SAFE", None

        # Fail closed.
        return "BLOCKED", "Action could not be validated."


# Quick self-test
if __name__ == "__main__":

    validator = SecurityValidator()

    print("\n--- APPLICATION TESTS ---")

    print(
        "Chrome:",
        validator.validate_application("chrome")
    )

    print(
        "Spotify:",
        validator.validate_application("spotify")
    )

    print(
        "Injection:",
        validator.validate_application("calc.exe & format C:")
    )

    print(
        "Blocked command:",
        validator.validate_application("del important.txt")
    )

    print(
        "Blocked script:",
        validator.validate_application("script.ps1")
    )

    print("\n--- FILE TESTS ---")

    print(
        "Resume:",
        validator.validate_file_name("resume.pdf")
    )

    print(
        "Traversal:",
        validator.validate_file_name("../secret.txt")
    )

    print(
        "Protected path:",
        validator.validate_file_path(
            r"C:\Windows\System32\cmd.exe"
        )
    )

    print("\n--- INTENT TESTS ---")

    print(
        "Open Chrome:",
        validator.validate_intent({
            "action": "open_application",
            "target": "chrome",
            "folder": None
        })
    )

    print(
        "Open file:",
        validator.validate_intent({
            "action": "open_file",
            "target": "resume.pdf",
            "folder": "Downloads"
        })
    )

    print(
        "Delete file:",
        validator.validate_intent({
            "action": "delete_file",
            "target": "resume.pdf",
            "folder": None
        })
    )

    print(
        "Unknown action:",
        validator.validate_intent({
            "action": "something_random",
            "target": "whatever",
            "folder": None
        })
    )