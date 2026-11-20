from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

from engine.core.ollama_service import (
    ensure_ollama_running,
    find_ollama_executable,
    get_installed_models,
    is_ollama_running,
    safe_ollama_call,
)


def test_find_ollama_executable():
    exe = find_ollama_executable()
    # On this machine, Ollama is installed in AppData
    assert exe is not None
    assert "ollama" in exe.lower()


def test_is_ollama_running_mocked():
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        assert is_ollama_running() is True


def test_is_ollama_running_failure_mocked():
    with patch("urllib.request.urlopen", side_effect=Exception("Connection refused")):
        assert is_ollama_running() is False


def test_ensure_ollama_running_already_active():
    with patch("engine.core.ollama_service.is_ollama_running", return_value=True):
        assert ensure_ollama_running(auto_start=False) is True


def test_ensure_ollama_running_starts_process():
    # Simulate not running initially, then running after start
    run_states = [False, False, True]

    def mock_is_running(*args, **kwargs):
        return run_states.pop(0) if run_states else True

    with patch("engine.core.ollama_service.is_ollama_running", side_effect=mock_is_running), \
         patch("engine.core.ollama_service.start_ollama_server") as mock_start, \
         patch("time.sleep"):
        mock_proc = MagicMock()
        mock_start.return_value = mock_proc

        result = ensure_ollama_running(timeout=5.0, auto_start=True)
        assert result is True
        assert mock_start.called


def test_safe_ollama_call_success():
    mock_fn = MagicMock(return_value={"message": {"content": "Hello"}})
    res = safe_ollama_call(mock_fn, "arg1", key="val")
    assert res == {"message": {"content": "Hello"}}
    mock_fn.assert_called_once_with("arg1", key="val")


def test_safe_ollama_call_recovers_from_disconnect():
    call_count = 0

    def mock_fn(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise ConnectionError("Failed to connect to Ollama.")
        return {"message": {"content": "Recovered!"}}

    with patch("engine.core.ollama_service.ensure_ollama_running", return_value=True) as mock_ensure:
        result = safe_ollama_call(mock_fn)
        assert result == {"message": {"content": "Recovered!"}}
        assert call_count == 2
        assert mock_ensure.called


def test_safe_ollama_call_raises_on_fatal_failure():
    def mock_fn(*args, **kwargs):
        raise ConnectionError("Failed to connect to Ollama.")

    with patch("engine.core.ollama_service.ensure_ollama_running", return_value=False):
        try:
            safe_ollama_call(mock_fn)
            assert False, "Should have raised ConnectionError"
        except ConnectionError as e:
            assert "Failed to connect" in str(e)

