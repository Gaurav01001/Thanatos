from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

# Add src to sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir / "src"))

from engine.audio.audio import is_wake_command
from engine.audio.wake import WakeWordDetector


def test_is_wake_command_exact():
    assert is_wake_command("wake up")
    assert is_wake_command("wakeup")
    assert is_wake_command("wake up thanatos")
    assert is_wake_command("hey thanatos")
    assert is_wake_command("thanatos")
    assert is_wake_command("start listening")
    assert is_wake_command("are you awake")
    assert is_wake_command("are you there")


def test_is_wake_command_punctuation_and_casing():
    assert is_wake_command("Wake up, Thanatos!")
    assert is_wake_command("Hey Thanatos?")
    assert is_wake_command("WAKE UP")
    assert is_wake_command("can you wake up")


def test_is_wake_command_ignores_general_speech():
    assert not is_wake_command("what is artificial intelligence")
    assert not is_wake_command("how does wake sleep cycle work in biology")
    assert not is_wake_command("open notepad")
    assert not is_wake_command("")


def test_wake_word_detector_initialization():
    mock_transcriber = MagicMock()
    detector = WakeWordDetector(transcriber=mock_transcriber, on_wake=lambda t: None)
    assert not detector.is_running
    assert not detector.is_paused


def test_wake_word_detector_pause_resume():
    mock_transcriber = MagicMock()
    detector = WakeWordDetector(transcriber=mock_transcriber, on_wake=lambda t: None)
    detector.pause()
    assert detector.is_paused
    detector.resume()
    assert not detector.is_paused

