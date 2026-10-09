from __future__ import annotations

import asyncio
import io
import os
import re
import wave
from typing import ClassVar

import numpy as np
import sounddevice as sd
import soundfile as sf
from piper import PiperVoice
from piper.config import SynthesisConfig

try:
    from engine.core.logging import get_logger
except ImportError:
    from src.engine.core.logging import get_logger

logger = get_logger("tts")


def clean_text_for_speech(text: str) -> str:
    """
    Cleans raw markdown and system syntax so the AI voice speaks naturally
    with smooth cadence instead of reciting raw syntax, brackets, or code.
    """
    if not text:
        return ""

    # 1. Replace multi-line code blocks with a natural conversational sentence
    text = re.sub(r"```[\s\S]*?```", " I have generated the relevant code on your screen. ", text)

    # 2. Strip inline code backticks (`code` -> code)
    text = re.sub(r"`([^`]+)`", r"\1", text)

    # 3. Strip citation markers like [Source 1], [Source 1, 2], [Source 2-4]
    text = re.sub(r"\[Source\s*[\d,\s-]+\]", "", text, flags=re.IGNORECASE)

    # 4. Remove Markdown headers (#, ##, ###)
    text = re.sub(r"^#+\s*", "", text, flags=re.MULTILINE)

    # 5. Remove bold and italic markers (**bold** -> bold, *italic* -> italic)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    text = re.sub(r"__([^_]+)__", r"\1", text)

    # 6. Replace URLs with simple word 'link'
    text = re.sub(r"https?://\S+", "link", text)

    # 7. Clean bullet list markers (*, -, •)
    text = re.sub(r"^\s*[-*•]\s+", "", text, flags=re.MULTILINE)

    # 8. Collapse whitespace into clean single spaces
    text = re.sub(r"\s+", " ", text).strip()

    # 9. Ensure ending punctuation for natural vocal cadence
    if text and not text.endswith((".", "!", "?")):
        text += "."

    return text


class TextToSpeech:
    """
    High-Fidelity Multi-Engine Text-to-Speech System:
    - Profiles:
        - "jarvis": Deep, composed, suave British cadence (Paul Bettany style)
        - "mentalist": Soothing, relaxed, observant cadence (Patrick Jane style)
        - "soothing": Warm, reassuring, empathetic tone
        - "calm": Deep, grounded American assistant
    - Engine Tiers:
        1. Tier 1: ElevenLabs AI Voice (if ELEVENLABS_API_KEY is configured)
        2. Tier 2: Microsoft Neural Edge-TTS (100% free, studio quality, zero API key)
        3. Tier 3: Piper Local ONNX Voice (offline fallback)
    """

    VOICE_PROFILES: ClassVar[dict[str, dict[str, str]]] = {
        "jarvis": {
            "edge_voice": "en-GB-RyanNeural",
            "rate": "-3%",
            "pitch": "-2Hz",
            "eleven_id": "onwK4e9ZLuTAKqWW03F9",  # Daniel (Refined British)
            "description": "Deep, calm, suave British intelligence (JARVIS)",
        },
        "mentalist": {
            "edge_voice": "en-AU-WilliamMultilingualNeural",
            "rate": "-4%",
            "pitch": "-1Hz",
            "eleven_id": "JBFqnCBsd6RMkjVDRZzb",  # George (Warm, insightful)
            "description": "Soothing, relaxed, observant cadence (Patrick Jane style)",
        },
        "soothing": {
            "edge_voice": "en-US-AndrewMultilingualNeural",
            "rate": "-4%",
            "pitch": "-1Hz",
            "eleven_id": "pNInz6obpgDQGcFmaJgB",  # Adam (Warm deep)
            "description": "Warm, reassuring, empathetic tone",
        },
        "calm": {
            "edge_voice": "en-US-BrianMultilingualNeural",
            "rate": "-3%",
            "pitch": "-2Hz",
            "eleven_id": "pNInz6obpgDQGcFmaJgB",
            "description": "Deep, grounded, composed modern assistant",
        },
    }

    def __init__(
        self,
        profile: str = "jarvis",
        speed: float = 1.15,
        edge_voice: str | None = None,
        rate: str | None = None,
        pitch: str | None = None,
        eleven_voice_id: str | None = None,
    ) -> None:
        selected_profile = os.environ.get("THANATOS_VOICE", profile).lower().strip()
        prof_data = self.VOICE_PROFILES.get(selected_profile, self.VOICE_PROFILES["jarvis"])

        self.profile = selected_profile
        self.speed = speed
        self.edge_voice = edge_voice or prof_data["edge_voice"]
        self.rate = rate or prof_data.get("rate", "-3%")
        self.pitch = pitch or prof_data.get("pitch", "-2Hz")
        self.eleven_voice_id = eleven_voice_id or prof_data["eleven_id"]
        self.eleven_api_key = os.environ.get("ELEVENLABS_API_KEY", "").strip()

        # Offline local fallback voice
        self._piper_voice: PiperVoice | None = None
        self._piper_config = SynthesisConfig(length_scale=speed)
        self._load_local_piper()

    def _load_local_piper(self) -> None:
        """Loads offline Piper ONNX model as fallback."""
        try:
            model_path = "en_US-ryan-medium.onnx"
            if os.path.exists(model_path):
                self._piper_voice = PiperVoice.load(model_path)
            else:
                logger.warning("Local Piper model %s not found.", model_path)
        except Exception as e:  # noqa: BLE001
            logger.warning("Failed to initialize local Piper voice: %s", e)

    def speak(self, text: str) -> None:
        """Main vocalization method with smart sanitization and graceful fallback."""
        if not text or not text.strip():
            return

        clean_text = clean_text_for_speech(text)
        if not clean_text:
            return

        # 1. Try ElevenLabs if API key is provided
        if self.eleven_api_key:
            try:
                if self._speak_elevenlabs(clean_text):
                    return
            except Exception as e:  # noqa: BLE001
                logger.warning("ElevenLabs TTS failed: %s. Falling back to Edge-TTS.", e)

        # 2. Try High-Quality Neural Edge-TTS (Free, No API Key, Studio Quality)
        try:
            if self._speak_edge_tts(clean_text):
                return
        except Exception as e:  # noqa: BLE001
            logger.warning("Edge-TTS failed: %s. Falling back to offline Piper voice.", e)

        # 3. Fallback to Offline Piper ONNX
        self._speak_piper(clean_text)

    def _speak_elevenlabs(self, text: str) -> bool:
        """Synthesizes speech using ElevenLabs API."""
        try:
            from elevenlabs.client import ElevenLabs

            client = ElevenLabs(api_key=self.eleven_api_key)
            audio_generator = client.text_to_speech.convert(
                voice_id=self.eleven_voice_id,
                text=text,
                model_id="eleven_multilingual_v2",
                output_format="mp3_44100_128",
            )
            audio_bytes = b"".join(audio_generator)
            if not audio_bytes:
                return False

            self._play_audio_bytes(audio_bytes)
            return True
        except Exception as e:  # noqa: BLE001
            logger.warning("ElevenLabs request failed: %s", e)
            return False

    def _speak_edge_tts(self, text: str) -> bool:
        """Synthesizes speech using Microsoft Neural Edge-TTS."""
        import edge_tts

        async def _synthesize() -> bytes:
            communicate = edge_tts.Communicate(
                text,
                self.edge_voice,
                rate=self.rate,
                pitch=self.pitch,
            )
            audio_data = b""
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_data += chunk["data"]
            return audio_data

        try:
            audio_bytes = asyncio.run(_synthesize())
            if not audio_bytes:
                return False

            self._play_audio_bytes(audio_bytes)
            return True
        except Exception as e:  # noqa: BLE001
            logger.warning("Edge-TTS synthesis error: %s", e)
            return False

    def _speak_piper(self, text: str) -> None:
        """Local offline fallback using Piper ONNX."""
        if not self._piper_voice:
            logger.error("No TTS engine available to speak.")
            return

        try:
            temp_wav = "output.wav"
            with wave.open(temp_wav, "wb") as wav_file:
                self._piper_voice.synthesize_wav(text, wav_file, syn_config=self._piper_config)

            audio, sample_rate = sf.read(temp_wav)
            padded_audio = np.pad(audio, (0, int(sample_rate * 0.3)))
            sd.play(padded_audio, sample_rate)
            sd.wait()
        except Exception as e:  # noqa: BLE001
            logger.error("Piper offline fallback failed: %s", e)

    def _play_audio_bytes(self, audio_bytes: bytes) -> None:
        """Decodes in-memory MP3/WAV bytes and plays smoothly via sounddevice."""
        audio_stream = io.BytesIO(audio_bytes)
        audio_data, sample_rate = sf.read(audio_stream)

        # Pad 250ms of silence at the end to prevent buffer clipping
        padded_audio = np.pad(audio_data, (0, int(sample_rate * 0.25)))
        sd.play(padded_audio, sample_rate)
        sd.wait()


if __name__ == "__main__":
    import sys

    profile_to_test = sys.argv[1] if len(sys.argv) > 1 else "jarvis"
    tts = TextToSpeech(profile=profile_to_test)
    test_msg = (
        f"Good morning. I am operational in {profile_to_test} mode. "
        "Take your time, observed every detail, and we shall proceed when you are ready."
    )
    print(f"Testing profile: {profile_to_test} ({tts.VOICE_PROFILES.get(profile_to_test, {}).get('description')})...")
    tts.speak(test_msg)
    print("Speech test completed!")