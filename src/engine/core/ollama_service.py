from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable

try:
    from engine.core.logging import get_logger
except (ImportError, ValueError):
    from src.engine.core.logging import get_logger

logger = get_logger("ollama_service")

DEFAULT_OLLAMA_URL = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
_ollama_process: subprocess.Popen | None = None
_start_lock = threading.Lock()
_is_starting = False


def find_ollama_executable() -> str | None:
    """Finds the Ollama executable on the system across standard paths."""
    # 1. System PATH
    for name in ("ollama", "ollama.exe"):
        found = shutil.which(name)
        if found:
            return found

    # 2. Standard Windows installation paths
    if sys.platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA")
        program_files = os.environ.get("ProgramFiles")
        candidates: list[Path] = []

        if local_app_data:
            candidates.extend([
                Path(local_app_data) / "Programs" / "Ollama" / "ollama.exe",
                Path(local_app_data) / "Programs" / "Ollama" / "ollama app.exe",
            ])
        if program_files:
            candidates.extend([
                Path(program_files) / "Ollama" / "ollama.exe",
            ])

        home_cand = Path.home() / "AppData" / "Local" / "Programs" / "Ollama" / "ollama.exe"
        candidates.append(home_cand)

        for cand in candidates:
            if cand.exists():
                return str(cand)

    # 3. Unix standard paths
    for unix_path in ("/usr/local/bin/ollama", "/usr/bin/ollama", "/opt/homebrew/bin/ollama"):
        if os.path.exists(unix_path):
            return unix_path

    return None


def is_ollama_running(url: str = DEFAULT_OLLAMA_URL, timeout: float = 0.8) -> bool:
    """Checks whether the Ollama server is responding to HTTP requests."""
    check_url = f"{url.rstrip('/')}/api/version"
    try:
        req = urllib.request.Request(check_url, headers={"User-Agent": "Thanatos-OllamaService"})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.status == 200
    except Exception:
        return False


def start_ollama_server() -> subprocess.Popen | None:
    """Spawns Ollama server in background completely silently without popping up any shell window."""
    global _ollama_process

    if is_ollama_running():
        return _ollama_process

    exe_path = find_ollama_executable()
    if not exe_path:
        logger.warning("Ollama executable not found on system PATH or default directories.")
        return None

    logger.info("Starting Ollama server in background: %s", exe_path)

    cmd = [exe_path]
    # If using ollama.exe, pass 'serve'; if using 'ollama app.exe', launch the app directly
    if not exe_path.lower().endswith("ollama app.exe"):
        cmd.append("serve")

    try:
        if sys.platform == "win32":
            # SW_HIDE (0) + STARTF_USESHOWWINDOW + CREATE_NO_WINDOW guarantees 0 window flashing
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0  # SW_HIDE
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)

            proc = subprocess.Popen(
                cmd,
                startupinfo=startupinfo,
                creationflags=creationflags,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                close_fds=True,
            )
        else:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
            )

        _ollama_process = proc
        return proc
    except Exception as e:
        logger.error("Failed to spawn Ollama server process: %s", e)
        return None


def ensure_ollama_running(
    timeout: float = 12.0,
    auto_start: bool = True,
    url: str = DEFAULT_OLLAMA_URL,
) -> bool:
    """
    Ensures that Ollama is up and accessible.
    Thread-safe: only one server startup process is ever spawned at a time.
    Returns True if Ollama is running and responsive, False otherwise.
    """
    if is_ollama_running(url=url):
        return True

    if not auto_start:
        return False

    global _is_starting
    with _start_lock:
        # Double-check inside lock
        if is_ollama_running(url=url):
            return True

        if not _is_starting:
            _is_starting = True
            try:
                logger.info("Ollama is not running. Launching background Ollama server...")
                start_ollama_server()
            finally:
                _is_starting = False

    # Wait for Ollama to become healthy
    start_time = time.time()
    while time.time() - start_time < timeout:
        time.sleep(0.4)
        if is_ollama_running(url=url):
            logger.info("Ollama server is active and responding (took %.1fs).", time.time() - start_time)
            return True

    logger.warning("Ollama server did not respond within %.1f seconds.", timeout)
    return False


def safe_ollama_call(call_fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """
    Executes an Ollama API call with automatic recovery.
    If a connection error occurs, attempts to start/reconnect to Ollama and retries once.
    """
    try:
        return call_fn(*args, **kwargs)
    except Exception as e:
        err_msg = str(e).lower()
        if (
            "connect" in err_msg
            or "refused" in err_msg
            or "httpx" in err_msg
            or "connectionerror" in err_msg
            or "failed to connect" in err_msg
        ):
            logger.info("Ollama connection error encountered: %s. Attempting to start/reconnect server...", e)
            if ensure_ollama_running(timeout=12.0):
                logger.info("Ollama server is ready. Retrying request...")
                return call_fn(*args, **kwargs)
        raise


def get_installed_models(url: str = DEFAULT_OLLAMA_URL) -> list[str]:
    """Retrieves list of installed model names from Ollama."""
    tags_url = f"{url.rstrip('/')}/api/tags"
    try:
        import json
        req = urllib.request.Request(tags_url, headers={"User-Agent": "Thanatos-OllamaService"})
        with urllib.request.urlopen(req, timeout=2.0) as response:
            data = json.loads(response.read().decode("utf-8"))
            return [m.get("name", "") for m in data.get("models", [])]
    except Exception as e:
        logger.debug("Could not fetch installed models list: %s", e)
        return []
