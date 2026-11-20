from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Optional

import ollama

try:
    from engine.core.ollama_service import safe_ollama_call
except (ImportError, ValueError):
    from src.engine.core.ollama_service import safe_ollama_call

logger = logging.getLogger(__name__)


@dataclass
class MentorResponse:
    """Structured response from the DSA Mentor."""
    display_text: str
    speech_text: str
    problem_title: Optional[str] = None
    bottleneck: Optional[str] = None
    mode: str = "hint"


class DSAMentor:
    """
    Screen-aware LeetCode and DSA algorithmic mentor.
    
    Provides Socratic algorithmic guidance without prematurely spoiling
    complete code solutions.
    """

    def __init__(self, model: str = "gemma3:4b") -> None:
        self.model = model

    def _build_prompt(self, query: str = "", mode: str = "hint") -> str:
        """Constructs a strict Socratic mentoring prompt based on the user's intent."""
        
        base_rules = (
            "You are Thanatos DSA Mentor, a world-class competitive programming and algorithms coach.\n"
            "Examine this screenshot of the user's coding environment (e.g. LeetCode, HackerRank, IDE, or terminal).\n\n"
            "CRITICAL INSTRUCTIONS:\n"
            "1. Identify the problem name, constraints, and the user's current code/approach.\n"
            "2. Identify any visible test case failures, runtime errors, or performance bottlenecks.\n"
        )

        if mode == "hint":
            instructions = (
                f"{base_rules}"
                "3. DO NOT write or reveal the full code solution.\n"
                "4. Provide a Socratic algorithmic hint: explain the intuition or data structure that unlocks the optimal approach.\n"
                "5. Keep the vocal takeaway to exactly 1 or 2 crisp sentences.\n\n"
                "Format your response EXACTLY as follows:\n"
                "### Problem: <Problem Title or 'Unknown'>\n"
                "### Detected Approach: <Brief summary of user's code>\n"
                "### Bottleneck: <What causes TLE, wrong answer, or inefficiency>\n"
                "### Socratic Hint: <2-4 sentences explaining intuition/data structure>\n"
                "### Vocal Nudge: <Exactly 1-2 punchy sentences to be spoken aloud into headphones>\n"
            )
        elif mode == "debug":
            instructions = (
                f"{base_rules}"
                "3. Focus on why the current test case failed or why a runtime error occurred.\n"
                "4. Highlight edge cases (e.g. empty inputs, zero, negative values, off-by-one indices).\n"
                "5. Format with: ### Problem, ### Bug/Edge Case, ### Recommended Fix, ### Vocal Nudge.\n"
            )
        elif mode == "complexity":
            instructions = (
                f"{base_rules}"
                "3. State the Time and Space Complexity of the user's visible code.\n"
                "4. State the Optimal Time and Space Complexity expected for this problem.\n"
                "5. Format with: ### Problem, ### Current Complexity, ### Optimal Complexity, ### Vocal Nudge.\n"
            )
        else:  # Full solution (only if user explicitly asked)
            instructions = (
                f"{base_rules}"
                "3. Provide the clean, optimal solution code with brief line comments explaining the algorithm.\n"
                "4. Include Time and Space Complexity.\n"
                "5. Include a 1-sentence Vocal Nudge.\n"
            )

        if query:
            instructions += f"\nUser's specific inquiry: \"{query}\"\n"

        return instructions

    def analyze_screen(
        self,
        image_path: str,
        query: str = "",
        mode: str = "hint",
    ) -> MentorResponse:
        """
        Analyzes screenshot with the local vision model and returns dual-track mentoring guidance.
        """
        prompt = self._build_prompt(query=query, mode=mode)

        try:
            response = safe_ollama_call(
                ollama.chat,
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                        "images": [image_path],
                    }
                ],
            )
            raw_text = response.message.content.strip()
            return self._parse_mentor_output(raw_text, mode=mode)

        except Exception as e:
            logger.error("DSA Mentor vision analysis failed: %s", e)
            err_msg = f"Vision analysis failed: {e}"
            return MentorResponse(
                display_text=err_msg,
                speech_text="I couldn't analyze your screen right now. Please check if Ollama vision is running.",
                mode=mode,
            )

    def _parse_mentor_output(self, raw_text: str, mode: str) -> MentorResponse:
        """Extracts structured sections and spoken whisper from the vision model's output."""
        # 1. Extract Vocal Nudge if present
        vocal_match = re.search(r"###\s*Vocal Nudge:\s*(.+?)(?:\n###|$)", raw_text, re.DOTALL | re.IGNORECASE)
        if vocal_match:
            speech_text = vocal_match.group(1).strip()
            # Clean up display text so Vocal Nudge header isn't duplicated awkwardly
            display_text = raw_text
        else:
            # Fallback: Extract first 1-2 sentences of Socratic Hint or raw text
            hint_match = re.search(r"###\s*Socratic Hint:\s*(.+?)(?:\n###|$)", raw_text, re.DOTALL | re.IGNORECASE)
            source = hint_match.group(1).strip() if hint_match else raw_text
            clean = re.sub(r"[#*`]", "", source).strip()
            sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", clean) if s.strip()]
            speech_text = " ".join(sentences[:2]) if sentences else "Here is an algorithmic nudge for your problem."
            display_text = raw_text

        # 2. Extract Problem Title
        prob_match = re.search(r"###\s*Problem:\s*(.+?)(?:\n|$)", raw_text, re.IGNORECASE)
        problem_title = prob_match.group(1).strip() if prob_match else None

        # 3. Extract Bottleneck
        bottleneck_match = re.search(r"###\s*Bottleneck:\s*(.+?)(?:\n###|$)", raw_text, re.DOTALL | re.IGNORECASE)
        bottleneck = bottleneck_match.group(1).strip() if bottleneck_match else None

        return MentorResponse(
            display_text=display_text,
            speech_text=speech_text,
            problem_title=problem_title,
            bottleneck=bottleneck,
            mode=mode,
        )
