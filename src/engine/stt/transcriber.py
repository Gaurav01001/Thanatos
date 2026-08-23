import numpy as np
from faster_whisper import WhisperModel

class Transcriber:

    def __init__(self):
        self.model = WhisperModel("small", device="cpu", compute_type="int8")

    def transcribe(self, audio):
        if audio is None:
            return ""
        if isinstance(audio, np.ndarray):
            audio = audio.flatten().astype(np.float32)
        if len(audio) == 0:
            return ""
        segments, info = self.model.transcribe(audio)
        text = " ".join(segment.text for segment in segments)
        return text.strip()

if __name__ == "__main__":
    from engine.audio.audio import AudioInput
    audio_input = AudioInput()
    transcriber = Transcriber()

    print("Speak Now")
    audio = audio_input.record()
    text = transcriber.transcribe(audio)
    