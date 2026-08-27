import os
from datetime import datetime
import mss

class ScreenCapture:

    def __init__(self, save_directory: str = "screenshots"):
        self.save_directory = save_directory
        os.makedirs(self.save_directory, exist_ok=True)

    def capture(self) -> str:

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"screenshot_{timestamp}.png"
        filepath = os.path.join(self.save_directory, filename)

        with mss.mss() as sct:
            monitor = sct.monitors[1]
            
            screenshot = sct.grab(monitor)
            mss.tools.to_png(screenshot.rgb, screenshot.size, output=filepath)
            return filepath

if __name__ == "__main__":

    screen = ScreenCapture()

    print("Taking screenshot...")

    path = screen.capture()

    print(f"Screenshot saved: {path}")

#   ┌────────────────────────────┐
#   │     Thanatos System        │
#   │                            │
#   │   ┌────────────────────┐   │
#   │   │  User Interaction  │   │
#   │   │       (Voice)      │   │
#   │   └───────────┬────────┘   │
#   │               │            │
#   │   ┌───────────▼────────────┐ │
#   │   │  Analyze Screenshot    │ │
#   │   │  (Brain + Vision)    │ │
#   │   └───────────┬────────────┘ │
#   │               │              │
#   │   ┌───────────▼────────────┐ │
#   │   │  Create Textual      │ │
#   │   │  Description         │ │
#   │   └───────────┬────────────┘ │
#   │               │              │
#   │   ┌───────────▼────────────┐ │
#   │   │  Brain Analyzes      │ │
#   │   │  intent + screenshot │ │
#   │   └───────────┬────────────┘ │
#   │               │              │
#   │   ┌───────────▼────────────┐ │
#   │   │  Executor Takes Action │ │
#   │   └───────────┬────────────┘ │
#   │               │              │
#   │   ┌───────────▼────────────┐ │
#   │   │   Update UI / Audio    │ │
#   └────────────────────────────┘