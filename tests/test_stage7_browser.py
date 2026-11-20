import unittest
from unittest.mock import MagicMock, patch
from src.engine.browser.browser_agent import BrowserAgent
from src.engine.security.validator import SecurityValidator


class TestStage7Browser(unittest.TestCase):
    def setUp(self):
        self.validator = SecurityValidator()
        self.agent = BrowserAgent(headless=True, timeout_ms=5000)

    def test_url_sanitization_and_precautions(self):
        # 1. Normalizes scheme-less URLs to https
        is_safe, norm_url, err = BrowserAgent.sanitize_and_validate_url("github.com/trending")
        self.assertTrue(is_safe)
        self.assertEqual(norm_url, "https://github.com/trending")
        self.assertIsNone(err)

        # 2. Accepts valid http/https URLs
        is_safe, norm_url, err = BrowserAgent.sanitize_and_validate_url("https://www.python.org")
        self.assertTrue(is_safe)
        self.assertEqual(norm_url, "https://www.python.org")

        # 3. Blocks dangerous local file schemes
        is_safe, norm_url, err = BrowserAgent.sanitize_and_validate_url("file:///C:/Windows/System32")
        self.assertFalse(is_safe)
        self.assertIn("Blocked unsafe URL scheme", err)

        # 4. Blocks javascript execution scheme
        is_safe, norm_url, err = BrowserAgent.sanitize_and_validate_url("javascript:alert(document.cookie)")
        self.assertFalse(is_safe)
        self.assertIn("Blocked unsafe URL scheme", err)

        # 5. Blocks data URI scheme
        is_safe, norm_url, err = BrowserAgent.sanitize_and_validate_url("data:text/html,<h1>hacked</h1>")
        self.assertFalse(is_safe)
        self.assertIn("Blocked unsafe URL scheme", err)

        # 6. Blocks loopback cloud metadata IP probing
        is_safe, norm_url, err = BrowserAgent.sanitize_and_validate_url("http://169.254.169.254/latest/meta-data/")
        self.assertFalse(is_safe)
        self.assertIn("cloud metadata", err)

    def test_security_validator_browser_actions(self):
        # Safe URL intent
        status, reason = self.validator.validate_intent({
            "action": "browse_url",
            "target": "https://huggingface.co/models",
            "folder": None,
        })
        self.assertEqual(status, "SAFE")
        self.assertIsNone(reason)

        # Blocked dangerous scheme intent
        status, reason = self.validator.validate_intent({
            "action": "browse_url",
            "target": "file:///C:/Windows/win.ini",
            "folder": None,
        })
        self.assertEqual(status, "BLOCKED")
        self.assertIn("Unsafe URL scheme", reason)

        # Safe browser search intent
        status, reason = self.validator.validate_intent({
            "action": "browse_web",
            "target": "latest artificial intelligence papers",
            "folder": None,
        })
        self.assertEqual(status, "SAFE")
        self.assertIsNone(reason)

    @patch("src.engine.brain.brain.RAGManager")
    def test_brain_browser_intent_mapping(self, mock_rag):
        from src.engine.brain.brain import Brain
        brain = Brain()

        # Direct URL browsing
        intent1 = brain.get_intent("browse https://github.com")
        self.assertEqual(intent1["action"], "browse_url")
        self.assertEqual(intent1["target"], "https://github.com")

        # Domain browsing without explicit https
        intent2 = brain.get_intent("visit reddit.com")
        self.assertEqual(intent2["action"], "browse_url")
        self.assertEqual(intent2["target"], "reddit.com")

        # Web browsing search
        intent3 = brain.get_intent("search on browser for best mechanical keyboards")
        self.assertEqual(intent3["action"], "browse_web")
        self.assertIn("mechanical keyboards", intent3["target"])

    def test_browser_agent_lifecycle_mocked(self):
        # Verifies primitives work cleanly when page/context are mocked
        mock_page = MagicMock()
        mock_page.is_closed.return_value = False
        mock_page.title.return_value = "Python.org"
        mock_page.url = "https://www.python.org"
        mock_page.locator.return_value.count.return_value = 1
        mock_page.locator.return_value.first.inner_text.return_value = "Welcome to Python"

        self.agent._page = mock_page

        # 1. Navigate
        nav = self.agent.navigate("https://www.python.org")
        self.assertTrue(nav["success"])
        self.assertEqual(nav["title"], "Python.org")
        mock_page.goto.assert_called_once()

        # 2. Extract
        ext = self.agent.extract()
        self.assertTrue(ext["success"])
        self.assertIn("Python", ext["content"])

        # 3. Type
        typed = self.agent.type("asyncio", selector="#search", press_enter=True)
        self.assertTrue(typed)

        # 4. Click
        clicked = self.agent.click("#submit")
        self.assertTrue(clicked)

        # 5. Close
        self.agent.close()
        self.assertIsNone(self.agent._page)

    def test_quick_browse_recipe(self):
        with patch.object(self.agent, "navigate") as mock_nav, patch.object(self.agent, "extract") as mock_ext:
            mock_nav.return_value = {
                "success": True,
                "url": "https://news.ycombinator.com",
                "title": "Hacker News",
                "error": None,
            }
            mock_ext.return_value = {
                "success": True,
                "content": "Top stories today...",
                "title": "Hacker News",
            }

            res = self.agent.quick_browse("news.ycombinator.com")
            self.assertEqual(res["type"], "navigate")
            self.assertTrue(res["success"])
            self.assertIn("Hacker News", res["summary"])

    def test_live_playwright_end_to_end(self):
        # Live headless browser verification
        agent = BrowserAgent(headless=True, timeout_ms=10000)
        try:
            nav = agent.navigate("https://example.com")
            self.assertTrue(nav["success"])
            self.assertEqual(nav["title"], "Example Domain")

            ext = agent.extract()
            self.assertTrue(ext["success"])
            self.assertIn("documentation examples", ext["content"].lower())
            self.assertTrue(len(ext["content"]) > 50)
        finally:
            agent.close()


if __name__ == "__main__":
    unittest.main()
