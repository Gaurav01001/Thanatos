import sys
from pathlib import Path

# Ensure src is in sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir / "src"))

from engine.audio.audio import AudioInput, is_exit_command, is_sleep_command, play_chime


def test_is_sleep_command_phrases():
    # True positives: intentional sleep/quiet phrases
    assert is_sleep_command("go to sleep")
    assert is_sleep_command("Thanatos, go to sleep please")
    assert is_sleep_command("I'm not talking to you")
    assert is_sleep_command("im not talking to you")
    assert is_sleep_command("Okay that's all for now")
    assert is_sleep_command("thats all")
    assert is_sleep_command("shut up")
    assert is_sleep_command("be quiet")
    assert is_sleep_command("stop listening")
    assert is_sleep_command("sleep")
    assert is_sleep_command("never mind")


def test_is_sleep_command_false_positives():
    # False positives: normal conversational queries that should NOT trigger sleep
    assert not is_sleep_command("How do I sleep better at night?")
    assert not is_sleep_command("Can you explain how sleeping threads work in Python?")
    assert not is_sleep_command("What is the weather in Kolkata?")
    assert not is_sleep_command("Write a quicksort in C++")
    assert not is_sleep_command("Who are you?")
    assert not is_sleep_command("")


def test_is_exit_command_phrases():
    # True positives: various voice and text ways to exit/close the assistant
    assert is_exit_command("exit")
    assert is_exit_command("EXIT")
    assert is_exit_command("/exit")
    assert is_exit_command("quit")
    assert is_exit_command("/quit")
    assert is_exit_command("close")
    assert is_exit_command("/close")
    assert is_exit_command("bye")
    assert is_exit_command("goodbye")
    assert is_exit_command("terminate")
    assert is_exit_command("terminate session")
    assert is_exit_command("close assistant")
    assert is_exit_command("close the assistant")
    assert is_exit_command("close the ai assistant")
    assert is_exit_command("close ai assistant")
    assert is_exit_command("close thanatos")
    assert is_exit_command("exit assistant")
    assert is_exit_command("exit thanatos")
    assert is_exit_command("shut down assistant")
    assert is_exit_command("shutdown assistant")
    assert is_exit_command("shut down thanatos")
    assert is_exit_command("shutdown thanatos")
    assert is_exit_command("turn off assistant")
    assert is_exit_command("turn off thanatos")
    assert is_exit_command("terminate assistant")
    assert is_exit_command("terminate thanatos")
    assert is_exit_command("please close the assistant")
    assert is_exit_command("can you exit thanatos")


def test_is_exit_command_false_positives():
    # False positives: general questions or commands on external apps
    assert not is_exit_command("Can you explain how to close a file in Python?")
    assert not is_exit_command("What is an exit code in Linux?")
    assert not is_exit_command("How do I exit vim?")
    assert not is_exit_command("Why did the window close unexpectedly?")
    assert not is_exit_command("Is there an exit nearby?")
    assert not is_exit_command("Close spotify")
    assert not is_exit_command("open the brave browser")
    assert not is_exit_command("what is your name?")
    assert not is_exit_command("")


def test_audio_input_init():
    audio = AudioInput(samplerate=16000)
    assert audio.samplerate == 16000


def test_play_chime_does_not_crash():
    # Verify play_chime handles wake and sleep syntheses without raising exceptions
    play_chime(kind="wake")
    play_chime(kind="sleep")
