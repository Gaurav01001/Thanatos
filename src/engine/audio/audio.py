import numpy as np
import sounddevice as sd
from pynput import keyboard


class AudioInput:

    def __init__(self, samplerate: int = 16000):
        self.device = sd.query_devices(kind="input")
        self.samplerate = samplerate

    def record(self):
        print("\r[Hold Space to speak, Esc to cancel]", end="", flush=True)
        frames = []
        is_recording = False
        cancelled = False

        def audio_callback(indata, frame_count, time_info, status):
            if is_recording:
                frames.append(indata.copy())

        stream = sd.InputStream(
            samplerate=self.samplerate,
            channels=1,
            dtype="float32",
            callback=audio_callback
        )

        def on_press(key):
            nonlocal is_recording, cancelled
            if key == keyboard.Key.space and not is_recording:
                is_recording = True
                print("\r[Recording... release Space to send]   ", end="", flush=True)
            elif key == keyboard.Key.esc:
                cancelled = True
                return False

        def on_release(key):
            nonlocal is_recording, cancelled
            if key == keyboard.Key.space and is_recording:
                is_recording = False
                print("\r[Transcribing...]                      ", end="", flush=True)
                return False  # Stop listener
            elif key == keyboard.Key.esc:
                cancelled = True
                return False

        with stream:
            with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
                listener.join()

        # Clear the status line
        print("\r" + " " * 45 + "\r", end="", flush=True)

        if cancelled:
            return None

        if frames:
            audio = np.concatenate(frames, axis=0)
            return audio.flatten()
        return np.array([], dtype=np.float32)


if __name__ == "__main__":
    audio = AudioInput()
    recording = audio.record()
    print("Recording complete!")
    print(f"Shape: {recording.shape}")

      