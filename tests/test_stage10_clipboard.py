import unittest
from unittest.mock import MagicMock, patch

from src.engine.clipboard.smart_fix import (
    SmartFixResult,
    build_smart_fix_system_prompt,
    detect_content_type,
    get_clipboard_text,
    parse_smart_fix_response,
    set_clipboard_text,
)
from src.engine.core.hotkey import HotkeyManager
from src.engine.security.validator import SecurityValidator


class TestStage10Clipboard(unittest.TestCase):
    def setUp(self):
        self.validator = SecurityValidator()

    # ------------------------------------------------------------------
    # 1. Content Type Detection Heuristics
    # ------------------------------------------------------------------
    def test_detect_traceback(self):
        tb = (
            "Traceback (most recent call last):\n"
            "  File 'app.py', line 42, in <module>\n"
            "    res = data['user_id']\n"
            "KeyError: 'user_id'"
        )
        self.assertEqual(detect_content_type(tb), "traceback")

        cpp_err = "fatal error: iostream: No such file or directory\n #include <iostream>"
        self.assertEqual(detect_content_type(cpp_err), "traceback")

    def test_detect_json(self):
        valid_json = '{"name": "Gaurav", "role": "engineer", "active": true}'
        self.assertEqual(detect_content_type(valid_json), "json")

        broken_json = '{"title": "Thanatos", "version": 0.1, "items": ['
        self.assertEqual(detect_content_type(broken_json), "json")

    def test_detect_code(self):
        python_code = (
            "def calculate_fibonacci(n: int) -> int:\n"
            "    if n <= 1:\n"
            "        return n\n"
            "    return calculate_fibonacci(n - 1) + calculate_fibonacci(n - 2)"
        )
        self.assertEqual(detect_content_type(python_code), "code")

        js_code = "const handleClick = (e) => { e.preventDefault(); console.log('clicked'); };"
        self.assertEqual(detect_content_type(js_code), "code")

    def test_detect_prose(self):
        prose = "Hey team, just wanted to check in on the milestone for the Q3 release schedule."
        self.assertEqual(detect_content_type(prose), "prose")

    def test_detect_empty(self):
        self.assertEqual(detect_content_type(""), "empty")
        self.assertEqual(detect_content_type("   \n\t  "), "empty")

    # ------------------------------------------------------------------
    # 2. Prompt Builder
    # ------------------------------------------------------------------
    def test_prompt_construction(self):
        tb_prompt = build_smart_fix_system_prompt("traceback")
        self.assertIn("expert software debugger", tb_prompt)
        self.assertIn("DIAGNOSIS:", tb_prompt)
        self.assertIn("FIX:", tb_prompt)

        json_prompt = build_smart_fix_system_prompt("json")
        self.assertIn("JSON", json_prompt)

        code_prompt = build_smart_fix_system_prompt("code")
        self.assertIn("principal software engineer", code_prompt)

        prose_prompt = build_smart_fix_system_prompt("prose")
        self.assertIn("editor", prose_prompt)

    # ------------------------------------------------------------------
    # 3. Response Parser
    # ------------------------------------------------------------------
    def test_parse_smart_fix_response_code(self):
        raw = (
            "DIAGNOSIS:\nThe dictionary key 'user_id' was missing because the payload was empty.\n\n"
            "FIX:\n```python\nuser_id = data.get('user_id', 'anonymous')\n```"
        )
        fixed_text, explanation, speech_text = parse_smart_fix_response(raw, "traceback")
        self.assertEqual(fixed_text, "user_id = data.get('user_id', 'anonymous')")
        self.assertIn("dictionary key", explanation)
        self.assertIn("copied to your clipboard", speech_text)

    def test_parse_smart_fix_response_prose(self):
        raw = (
            "DIAGNOSIS:\nFixed grammatical tense and enhanced professional tone.\n\n"
            "FIX:\nDear Team, please find attached the revised project roadmap for review."
        )
        fixed_text, explanation, speech_text = parse_smart_fix_response(raw, "prose")
        self.assertEqual(fixed_text, "Dear Team, please find attached the revised project roadmap for review.")
        self.assertIn("Fixed grammatical tense", explanation)
        self.assertIn("Polished text is copied to your clipboard", speech_text)

    # ------------------------------------------------------------------
    # 4. SecurityValidator Gate
    # ------------------------------------------------------------------
    def test_security_validator_smart_fix(self):
        status, reason = self.validator.validate_intent({
            "action": "smart_fix_clipboard",
            "target": None,
            "folder": None,
        })
        self.assertEqual(status, "SAFE")
        self.assertIsNone(reason)

    # ------------------------------------------------------------------
    # 5. Brain Intent Classification
    # ------------------------------------------------------------------
    @patch("src.engine.brain.brain.RAGManager")
    @patch("src.engine.brain.brain.KnowledgeRouter")
    @patch("src.engine.brain.brain.QueryCondenser")
    def test_brain_fast_path_smart_fix(self, mock_cond, mock_router, mock_rag):
        from src.engine.brain.brain import Brain

        brain = Brain()
        intent = brain.get_intent("smart fix")
        self.assertEqual(intent["action"], "smart_fix_clipboard")

        intent = brain.get_intent("fix my clipboard")
        self.assertEqual(intent["action"], "smart_fix_clipboard")

        intent = brain.get_intent("polish clipboard")
        self.assertEqual(intent["action"], "smart_fix_clipboard")

    # ------------------------------------------------------------------
    # 6. HotkeyManager Registration
    # ------------------------------------------------------------------
    def test_hotkey_manager_clipboard_registration(self):
        on_clip = MagicMock()
        manager = HotkeyManager(
            on_clipboard_trigger=on_clip,
            clipboard_hotkey="<ctrl>+<shift>+v",
        )
        self.assertEqual(manager.clipboard_hotkey_str, "<ctrl>+<shift>+v")

        # Debounced trigger call
        manager._handle_clipboard_trigger()
        on_clip.assert_called_once()


if __name__ == "__main__":
    unittest.main()
