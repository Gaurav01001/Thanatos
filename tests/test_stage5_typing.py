import unittest
from unittest.mock import MagicMock, patch
from src.engine.security.validator import SecurityValidator
from src.engine.executor.executor import Executor


class TestStage5Typing(unittest.TestCase):
    def setUp(self):
        self.validator = SecurityValidator()
        self.executor = Executor()

    def test_security_validator_safe_actions(self):
        # write_text and paste_text should be classified as SAFE
        status, reason = self.validator.validate_intent({
            "action": "write_text",
            "target": "an email asking for extension on project",
            "folder": None,
        })
        self.assertEqual(status, "SAFE")
        self.assertIsNone(reason)

        status, reason = self.validator.validate_intent({
            "action": "paste_text",
            "target": "print('hello')",
            "folder": None,
        })
        self.assertEqual(status, "SAFE")
        self.assertIsNone(reason)

    def test_security_validator_confirm_actions(self):
        # send_email and send_message should require CONFIRM
        status, reason = self.validator.validate_intent({
            "action": "send_email",
            "target": "manager@company.com",
            "folder": None,
        })
        self.assertEqual(status, "CONFIRM")
        self.assertIn("send_email", reason)

        status, reason = self.validator.validate_intent({
            "action": "send_message",
            "target": "team channel",
            "folder": None,
        })
        self.assertEqual(status, "CONFIRM")
        self.assertIn("send_message", reason)

    def test_executor_paste_text_empty(self):
        self.assertFalse(self.executor.paste_text(""))
        self.assertFalse(self.executor.paste_text(None))

    @patch("src.engine.executor.executor.win32clipboard")
    @patch("src.engine.executor.executor.Controller")
    def test_executor_paste_text_success(self, mock_controller_cls, mock_clipboard):
        mock_kb = MagicMock()
        mock_controller_cls.return_value = mock_kb

        res = self.executor.paste_text("Hello Thanatos!")
        self.assertTrue(res)

        mock_clipboard.OpenClipboard.assert_called_once()
        mock_clipboard.EmptyClipboard.assert_called_once()
        mock_clipboard.SetClipboardData.assert_called_once()
        mock_clipboard.CloseClipboard.assert_called_once()
        self.assertTrue(mock_kb.press.called)
        self.assertTrue(mock_kb.release.called)

    @patch("src.engine.brain.brain.RAGManager")
    def test_brain_intent_writing(self, mock_rag):
        from src.engine.brain.brain import Brain
        brain = Brain()

        intent1 = brain.get_intent("write an email asking for an extension on the project")
        self.assertEqual(intent1["action"], "write_text")
        self.assertIn("extension on the project", intent1["target"])

        intent2 = brain.get_intent("type hello world into my editor")
        self.assertEqual(intent2["action"], "write_text")
        self.assertIn("hello world", intent2["target"])

        intent3 = brain.get_intent("draft a resignation letter")
        self.assertEqual(intent3["action"], "write_text")
        self.assertIn("resignation letter", intent3["target"])

        intent4 = brain.get_intent("paste this code")
        self.assertEqual(intent4["action"], "paste_text")

    @patch("src.engine.brain.brain.safe_ollama_call")
    @patch("src.engine.brain.brain.RAGManager")
    def test_brain_draft_text(self, mock_rag, mock_ollama_call):
        from src.engine.brain.brain import Brain
        brain = Brain()

        mock_resp = MagicMock()
        mock_resp.message.content = "Dear Team,\nI am requesting a brief extension."
        mock_ollama_call.return_value = mock_resp

        draft = brain.draft_text("email asking for extension")
        self.assertIn("Dear Team", draft)
        self.assertIn("extension", draft)
        mock_ollama_call.assert_called_once()


if __name__ == "__main__":
    unittest.main()
