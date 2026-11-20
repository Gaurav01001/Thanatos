from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

# Maximum characters accepted from clipboard to prevent token explosion
MAX_CLIPBOARD_CHARS = 25000


@dataclass
class SmartFixResult:
    """Represents the structured result of a Clipboard Smart Fix operation."""
    content_type: str
    original_text: str
    fixed_text: str
    explanation: str
    speech_text: str


def get_clipboard_text(max_chars: int = MAX_CLIPBOARD_CHARS) -> str:
    """
    Safely retrieves text from the Windows clipboard.
    Returns empty string if clipboard is empty, locked, or non-text.
    """
    text = ""
    try:
        import win32clipboard
        import win32con

        win32clipboard.OpenClipboard()
        try:
            if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
                data = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
                text = str(data or "").strip()
        finally:
            win32clipboard.CloseClipboard()
    except Exception as e:
        logger.warning("Failed to read clipboard via win32clipboard (%s). Trying ctypes fallback.", e)
        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            
            CF_UNICODETEXT = 13
            if user32.OpenClipboard(None):
                try:
                    handle = user32.GetClipboardData(CF_UNICODETEXT)
                    if handle:
                        kernel32.GlobalLock.restype = wintypes.LPCWSTR
                        ptr = kernel32.GlobalLock(handle)
                        if ptr:
                            text = str(ptr).strip()
                            kernel32.GlobalUnlock(handle)
                finally:
                    user32.CloseClipboard()
        except Exception as err:
            logger.error("Clipboard read fallback failed: %s", err)

    if len(text) > max_chars:
        logger.info("Clipboard text exceeded %d chars; safely truncating.", max_chars)
        text = text[:max_chars]

    return text


def set_clipboard_text(text: str) -> bool:
    """
    Safely writes unicode text to the Windows clipboard.
    """
    if text is None:
        return False

    try:
        import win32clipboard
        import win32con

        win32clipboard.OpenClipboard()
        try:
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
            return True
        finally:
            win32clipboard.CloseClipboard()
    except Exception as e:
        logger.warning("Failed to write clipboard via win32clipboard: %s", e)
        try:
            import ctypes

            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32

            CF_UNICODETEXT = 13
            GMEM_MOVEABLE = 0x0002

            encoded = text.encode("utf-16le") + b"\x00\x00"
            h_mem = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(encoded))
            if not h_mem:
                return False

            ptr = kernel32.GlobalLock(h_mem)
            if not ptr:
                kernel32.GlobalFree(h_mem)
                return False

            ctypes.memmove(ptr, encoded, len(encoded))
            kernel32.GlobalUnlock(h_mem)

            if user32.OpenClipboard(None):
                try:
                    user32.EmptyClipboard()
                    user32.SetClipboardData(CF_UNICODETEXT, h_mem)
                    return True
                finally:
                    user32.CloseClipboard()
        except Exception as err:
            logger.error("Clipboard write fallback failed: %s", err)

    return False


def detect_content_type(text: str) -> str:
    """
    Heuristically classifies clipboard text into:
      - 'traceback': Compiler error, stack trace, or crash log
      - 'json': Minified or unformatted JSON / data structure
      - 'code': Programming code snippet (Python, JS, C++, Rust, etc.)
      - 'prose': English sentences, email, draft text, documentation
    """
    if not text or not text.strip():
        return "empty"

    clean = text.strip()

    # 1. Traceback / Exception / Crash heuristic
    traceback_patterns = [
        r"Traceback\s*\(most recent call last\):",
        r"(?:Exception|Error|Fatal|Panic):",
        r"at\s+[a-zA-Z0-9_.]+\s*\([^)]+\.py:\d+\)",
        r"File\s+\"[^\"]+\",\s+line\s+\d+",
        r"panic:\s+",
        r"Segmentation fault",
        r"NullPointerException",
        r"SyntaxError:",
        r"TypeError:",
        r"ValueError:",
        r"KeyError:",
        r"IndexError:",
    ]
    if any(re.search(pat, clean, re.IGNORECASE) for pat in traceback_patterns):
        return "traceback"

    # 2. JSON / Data Structure heuristic
    if clean.startswith(("{", "[")):
        try:
            json.loads(clean)
            return "json"
        except Exception:
            # Check if it looks like broken/raw JSON
            if re.search(r'["\']\s*:\s*', clean):
                return "json"

    # 3. Code heuristic (syntax markers, keywords, indentation)
    code_indicators = [
        r"\bdef\s+[a-zA-Z0-9_]+\s*\(",
        r"\bclass\s+[a-zA-Z0-9_]+",
        r"\bfunction\s+[a-zA-Z0-9_]*\s*\(",
        r"\bconst\s+[a-zA-Z0-9_]+\s*=",
        r"\blet\s+[a-zA-Z0-9_]+\s*=",
        r"\bimport\s+[\w.]+",
        r"\bfrom\s+[\w.]+\s+import\b",
        r"#include\s+<",
        r"\bpublic\s+static\s+void\b",
        r"\bfn\s+[a-zA-Z0-9_]+\s*\(",
        r"=>\s*\{",
        r";\s*$",
    ]
    if any(re.search(pat, clean, re.MULTILINE) for pat in code_indicators):
        return "code"

    # If it has multi-line structure with consistent indentation and operators
    lines = clean.splitlines()
    if len(lines) >= 3:
        code_lines = [l for l in lines if re.match(r"^(?:\s{2,}|\t|\s*[{}()\[\];])", l)]
        if len(code_lines) / len(lines) >= 0.5:
            return "code"

    # 4. Default: Prose / Natural Language Text
    return "prose"


def build_smart_fix_system_prompt(content_type: str) -> str:
    """
    Constructs a specialized, strict prompt for Qwen 7B to optimize quality and speed.
    """
    if content_type == "traceback":
        return (
            "You are an expert software debugger. "
            "The user will provide a stack trace or compiler error.\n"
            "Format your response EXACTLY as follows:\n\n"
            "DIAGNOSIS:\n<Explain the root cause and why it occurred in 1-2 concise sentences.>\n\n"
            "FIX:\n```<language>\n<The exact corrected code snippet or minimal fix ready to copy>\n```"
        )

    if content_type == "json":
        return (
            "You are a data formatting specialist. "
            "Format and repair the user's input into clean, properly indented JSON (2 spaces).\n"
            "Format your response EXACTLY as follows:\n\n"
            "DIAGNOSIS:\nFormatted and validated JSON structure.\n\n"
            "FIX:\n```json\n<valid indented JSON>\n```"
        )

    if content_type == "code":
        return (
            "You are a principal software engineer. "
            "Review the user's code snippet. Fix any syntax errors, logic bugs, edge cases, or performance bottlenecks.\n"
            "Format your response EXACTLY as follows:\n\n"
            "DIAGNOSIS:\n<Explain the bug or optimization in 1 concise sentence.>\n\n"
            "FIX:\n```<language>\n<The clean, corrected code snippet with zero unnecessary comments>\n```"
        )

    # Prose / English text
    return (
        "You are an expert editor and writing assistant. "
        "The user will provide rough text, an email draft, or notes.\n"
        "Polishing rules:\n"
        "1. Fix spelling, grammar, and punctuation.\n"
        "2. Enhance clarity, flow, and professional tone while preserving the core message.\n"
        "Format your response EXACTLY as follows:\n\n"
        "DIAGNOSIS:\n<1 short sentence summarizing the improvements made (e.g. 'Corrected grammatical tense and tightened tone.')>\n\n"
        "FIX:\n<The complete polished text without quotes or markdown code fences>"
    )


def parse_smart_fix_response(raw_text: str, content_type: str) -> tuple[str, str, str]:
    """
    Parses LLM output into (fixed_text, explanation, speech_text).
    """
    if not raw_text or not raw_text.strip():
        return ("", "No response generated.", "Could not generate fix.")

    clean = raw_text.strip()
    explanation = ""
    fixed_text = ""

    # Parse DIAGNOSIS
    diag_match = re.search(r"DIAGNOSIS:\s*(.+?)(?=\n\s*FIX:|\Z)", clean, re.DOTALL | re.IGNORECASE)
    if diag_match:
        explanation = diag_match.group(1).strip()

    # Parse FIX
    fix_match = re.search(r"FIX:\s*(.+)", clean, re.DOTALL | re.IGNORECASE)
    fix_block = fix_match.group(1).strip() if fix_match else clean

    # If code fence present, extract interior code
    code_match = re.search(r"```(?:\w+)?\n([\s\S]*?)```", fix_block)
    if code_match:
        fixed_text = code_match.group(1).strip()
    else:
        # Prose fix or raw code without fences
        fixed_text = fix_block.strip()
        # Clean stray backticks if present
        if fixed_text.startswith("```") and fixed_text.endswith("```"):
            fixed_text = fixed_text.strip("`").strip()

    if not explanation:
        if content_type == "traceback":
            explanation = "Identified error in stack trace and generated code fix."
        elif content_type == "json":
            explanation = "Validated and formatted JSON."
        elif content_type == "code":
            explanation = "Corrected code snippet and optimized syntax."
        else:
            explanation = "Polished grammar, tone, and readability."

    # Build punchy speech text (1 short sentence for Piper TTS)
    first_sentence = re.split(r"(?<=[.!?])\s+", explanation)[0].strip()
    if content_type in ("traceback", "code"):
        speech_text = f"{first_sentence} The solution is copied to your clipboard."
    elif content_type == "json":
        speech_text = "Cleaned up and formatted your JSON data. Copied to your clipboard."
    else:
        speech_text = f"{first_sentence} Polished text is copied to your clipboard."

    return fixed_text, explanation, speech_text
