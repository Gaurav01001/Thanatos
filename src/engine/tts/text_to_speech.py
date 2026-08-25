from piper import PiperVoice
import soundfile as sf
import sounddevice as sd
import numpy as np

import wave

from piper.config import SynthesisConfig

class TextToSpeech:

    def __init__(self, speed: float = 1.15):
        self.voice = PiperVoice.load("en_US-norman-medium.onnx")
        # length_scale > 1.0 slows down the speech rate for clearer pronunciation
        self.config = SynthesisConfig(length_scale=speed)

    def speak(self, text: str) -> None:
        if not text or not text.strip():
            return

        # Ensure text has punctuation at the end for proper intonation
        clean_text = text.strip()
        if not clean_text.endswith((".", "!", "?")):
            clean_text += "."

        with wave.open("output.wav", "wb") as wav_file:
            self.voice.synthesize_wav(clean_text, wav_file, syn_config=self.config)

        audio, sample_rate = sf.read("output.wav")

        # Add 300ms of silence padding at the end so the audio buffer doesn't clip the last word
        padded_audio = np.pad(audio, (0, int(sample_rate * 0.3)))

        sd.play(padded_audio, sample_rate)
        sd.wait()

if __name__ == "__main__":
    tts = TextToSpeech()
    tts.speak("Hello. I am Thanatos.")
    print("Speech generated!")