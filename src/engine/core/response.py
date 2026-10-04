from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Response:
    display_text: str          # Complete text for the terminal screen
    speech_text: str           # 1-2 sentence punchline for TTS
    sources: str | None = None # Verified citation cards
    is_muted: bool = False     # Voice state flag
    metadata: dict = field(default_factory=dict)

    def __iter__(self):
        yield self.display_text
        yield self.sources
     