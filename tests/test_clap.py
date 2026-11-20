import sys
from pathlib import Path

import numpy as np

# Ensure src is in sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir / "src"))

from engine.audio.clap import ClapDetector


def test_clap_detector_initialization():
    detector = ClapDetector(on_double_clap=lambda: None)
    assert not detector.is_running
    assert not detector.is_paused


def test_clap_detector_ignores_low_noise():
    double_clapped = False

    def on_clap():
        nonlocal double_clapped
        double_clapped = True

    detector = ClapDetector(on_double_clap=on_clap, threshold=0.25)

    # Low ambient noise (RMS ~ 0.01)
    ambient = np.random.normal(0, 0.01, 512).astype(np.float32)
    assert not detector.process_audio_chunk(ambient, timestamp=1.0)
    assert not detector.process_audio_chunk(ambient, timestamp=1.3)
    assert not double_clapped


def test_clap_detector_single_clap_does_not_trigger():
    detector = ClapDetector(on_double_clap=lambda: None, threshold=0.25)

    # Sharp impulse chunk (clap 1)
    clap1 = np.zeros(512, dtype=np.float32)
    clap1[100] = 0.8  # high peak, high crest factor
    assert not detector.process_audio_chunk(clap1, timestamp=1.0)


def test_clap_detector_double_clap_triggers_within_window():
    detector = ClapDetector(on_double_clap=lambda: None, threshold=0.25, min_gap=0.15, max_gap=0.75)

    # Sharp impulse chunk (clap 1)
    clap1 = np.zeros(512, dtype=np.float32)
    clap1[50] = 0.75
    # Sharp impulse chunk (clap 2)
    clap2 = np.zeros(512, dtype=np.float32)
    clap2[50] = 0.82

    # Clap 1 at t = 1.0s
    res1 = detector.process_audio_chunk(clap1, timestamp=1.0)
    assert not res1

    # Clap 2 at t = 1.35s (gap = 0.35s, perfectly within [0.15s, 0.75s])
    res2 = detector.process_audio_chunk(clap2, timestamp=1.35)
    assert res2


def test_clap_detector_ignores_gap_too_fast():
    detector = ClapDetector(on_double_clap=lambda: None, threshold=0.25, min_gap=0.15, max_gap=0.75)

    clap1 = np.zeros(512, dtype=np.float32)
    clap1[50] = 0.8

    detector.process_audio_chunk(clap1, timestamp=1.0)
    # Gap is 0.05s (too fast, e.g. reverberation echo)
    res2 = detector.process_audio_chunk(clap1, timestamp=1.05)
    assert not res2


def test_clap_detector_ignores_gap_too_slow():
    detector = ClapDetector(on_double_clap=lambda: None, threshold=0.25, min_gap=0.15, max_gap=0.75)

    clap1 = np.zeros(512, dtype=np.float32)
    clap1[50] = 0.8

    detector.process_audio_chunk(clap1, timestamp=1.0)
    # Gap is 1.5s (exceeds max_gap 0.75s)
    res2 = detector.process_audio_chunk(clap1, timestamp=2.5)
    assert not res2


def test_clap_detector_pause_and_resume():
    detector = ClapDetector(on_double_clap=lambda: None, threshold=0.25)
    clap = np.zeros(512, dtype=np.float32)
    clap[50] = 0.85

    detector.pause()
    assert detector.is_paused
    assert not detector.process_audio_chunk(clap, timestamp=1.0)

    detector.resume()
    assert not detector.is_paused


def test_clap_detector_resume_idempotent_does_not_clear_first_clap():
    """Verifies that calling resume() while already active does not erase an in-flight first clap."""
    detector = ClapDetector(on_double_clap=lambda: None, threshold=0.15)
    clap = np.zeros(512, dtype=np.float32)
    clap[50] = 0.5

    # First clap arrives at t = 1.0s
    detector.process_audio_chunk(clap, timestamp=1.0)
    assert detector._last_clap_time == 1.0

    # Unnecessary resume call (like loop polling)
    detector.resume()
    assert detector._last_clap_time == 1.0, "resume() must not clear _last_clap_time if not paused"

    # Second clap arrives at t = 1.35s
    res2 = detector.process_audio_chunk(clap, timestamp=1.35)
    assert res2 is True, "Double clap should trigger successfully"


def test_clap_detector_realistic_microphone_amplitude():
    """Verifies that realistic microphone acoustic transients (amplitude ~0.20) trigger."""
    triggered = False

    def on_clap():
        nonlocal triggered
        triggered = True

    detector = ClapDetector(on_double_clap=on_clap, threshold=0.15)
    chunk = np.random.normal(0, 0.01, 512).astype(np.float32)
    chunk[20] = 0.22  # Realistic room clap peak

    detector.process_audio_chunk(chunk, timestamp=2.0)
    res = detector.process_audio_chunk(chunk, timestamp=2.3)
    assert res is True

