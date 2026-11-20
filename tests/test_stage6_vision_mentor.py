import unittest
from unittest.mock import MagicMock, patch
from src.engine.vision.mentor import DSAMentor, MentorResponse
from src.engine.security.validator import SecurityValidator
from src.engine.core.hotkey import HotkeyManager


class TestStage6VisionMentor(unittest.TestCase):
    def setUp(self):
        self.mentor = DSAMentor(model="gemma3:4b")
        self.validator = SecurityValidator()

    def test_mentor_build_prompt_modes(self):
        # 1. Hint mode should enforce Socratic rules and no full code
        hint_prompt = self.mentor._build_prompt("help with two sum", mode="hint")
        self.assertIn("DO NOT write or reveal the full code solution", hint_prompt)
        self.assertIn("Socratic algorithmic hint", hint_prompt)

        # 2. Debug mode should focus on test cases
        debug_prompt = self.mentor._build_prompt("why did this fail", mode="debug")
        self.assertIn("test case failed", debug_prompt)

        # 3. Complexity mode should ask for time/space
        comp_prompt = self.mentor._build_prompt("complexity check", mode="complexity")
        self.assertIn("Time and Space Complexity", comp_prompt)

        # 4. Solution mode should provide optimal code
        sol_prompt = self.mentor._build_prompt("full solution", mode="solution")
        self.assertIn("optimal solution code", sol_prompt)

    def test_mentor_parse_output(self):
        sample_output = """### Problem: Longest Substring Without Repeating Characters
### Detected Approach: Brute-force checking all substrings with nested loops.
### Bottleneck: O(N^3) runtime causes Time Limit Exceeded on large inputs.
### Socratic Hint: Think about sliding a window over the string while maintaining a set or map of character indices.
### Vocal Nudge: Try using a sliding window with a set to shrink the search to linear time."""

        parsed = self.mentor._parse_mentor_output(sample_output, mode="hint")
        self.assertEqual(parsed.problem_title, "Longest Substring Without Repeating Characters")
        self.assertIn("O(N^3) runtime", parsed.bottleneck)
        self.assertEqual(parsed.speech_text, "Try using a sliding window with a set to shrink the search to linear time.")
        self.assertEqual(parsed.mode, "hint")

    @patch("src.engine.vision.mentor.safe_ollama_call")
    def test_mentor_analyze_screen(self, mock_call):
        mock_resp = MagicMock()
        mock_resp.message.content = """### Problem: Invert Binary Tree
### Detected Approach: Recursive traversal
### Bottleneck: Missing base case for empty node
### Socratic Hint: Consider what happens when root is None.
### Vocal Nudge: Add a base case returning None when the node is empty."""
        mock_call.return_value = mock_resp

        res = self.mentor.analyze_screen("dummy.png", query="give me a hint", mode="hint")
        self.assertEqual(res.problem_title, "Invert Binary Tree")
        self.assertIn("base case", res.speech_text)
        mock_call.assert_called_once()

    def test_security_validator_dsa_mentor(self):
        status, reason = self.validator.validate_intent({
            "action": "dsa_mentor",
            "target": "give me a hint",
            "folder": "hint",
        })
        self.assertEqual(status, "SAFE")
        self.assertIsNone(reason)

    @patch("src.engine.brain.brain.RAGManager")
    def test_brain_dsa_intents(self, mock_rag):
        from src.engine.brain.brain import Brain
        brain = Brain()

        hint_intent = brain.get_intent("can you give me a hint on this problem?")
        self.assertEqual(hint_intent["action"], "dsa_mentor")
        self.assertEqual(hint_intent["folder"], "hint")

        debug_intent = brain.get_intent("why does this test fail?")
        self.assertEqual(debug_intent["action"], "dsa_mentor")
        self.assertEqual(debug_intent["folder"], "debug")

        comp_intent = brain.get_intent("what is the time complexity of my code?")
        self.assertEqual(comp_intent["action"], "dsa_mentor")
        self.assertEqual(comp_intent["folder"], "complexity")

        sol_intent = brain.get_intent("show me the optimal solution")
        self.assertEqual(sol_intent["action"], "dsa_mentor")
        self.assertEqual(sol_intent["folder"], "solution")

    def test_hotkey_manager_multi_key(self):
        hud_mock = MagicMock()
        vision_mock = MagicMock()

        manager = HotkeyManager(
            hotkey="<ctrl>+<space>",
            on_trigger=hud_mock,
            vision_hotkey="<f8>",
            on_vision_trigger=vision_mock,
        )

        self.assertEqual(manager.hud_hotkey_str, "<ctrl>+<space>")
        self.assertEqual(manager.vision_hotkey_str, "<f8>")

        # Trigger both debounced handlers
        manager._handle_hud_trigger()
        hud_mock.assert_called_once()

        manager._handle_vision_trigger()
        vision_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
