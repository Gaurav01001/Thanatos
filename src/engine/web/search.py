from __future__ import annotations

import json
from pathlib import Path

from ddgs import DDGS


class WebSearchEngine:
    def __init__(self) -> None:
        # Load user location from config.json (defaults to Kolkata, India)
        self.location = "Kolkata, India"
        config_file = Path(__file__).resolve().parents[3] / "config.json"
        if config_file.exists():
            try:
                with open(config_file, "r", encoding="utf-8") as f:
                    self.location = json.load(f).get("location", self.location)
            except Exception:  # noqa: BLE001, S110
                pass

    def search(self, query: str, max_results: int = 4) -> list[dict]:
        """Searches DuckDuckGo and returns clean result dictionaries."""
        # Replace 'near me' with your city
        clean_query = query.replace("near me", f"in {self.location}")
        
        try:
            return list(DDGS().text(clean_query, max_results=max_results))
        except Exception:  # noqa: BLE001
            return []

    def format_context(self, results: list[dict]) -> tuple[str, str]:
        """Turns results into LLM prompt text and clickable citations."""
        if not results:
            return "", ""

        context_cards = []
        sources = []
        for i, r in enumerate(results, start=1):
            title = r.get("title", "")
            url = r.get("href", "")
            body = r.get("body", "")
            context_cards.append(f"[Web Result {i}]: {title} ({url})\n{body}")
            sources.append(f"[Web {i}: {title} ({url})]")

        return "\n\n".join(context_cards), "\n".join(sources)
