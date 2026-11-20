from __future__ import annotations

import json
import logging
import re
import urllib.parse
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class BrowserAgent:
    """
    Stage 7 Generic Browser Automation Agent.
    
    Provides high-reliability Playwright automation primitives:
      - navigate(url)
      - search(query)
      - click(selector_or_text)
      - type(text, selector)
      - extract(selector)
      - close()
    
    Includes safety guards against dangerous URL schemes, automatic browser recovery
    if closed by the user, and structured content extraction.
    """

    ALLOWED_SCHEMES = {"http", "https"}
    BLOCKED_SCHEMES = {"file", "javascript", "data", "vbscript", "about", "chrome"}

    def __init__(
        self,
        headless: Optional[bool] = None,
        timeout_ms: int = 15000,
        config_path: Optional[Path] = None,
    ) -> None:
        self.config_path = config_path or (Path(__file__).resolve().parents[3] / "config.json")
        config_data = self._load_config()
        browser_cfg = config_data.get("browser", {})

        # Configuration options with fallback defaults
        self.headless = (
            headless
            if headless is not None
            else browser_cfg.get("headless", False)
        )
        self.timeout_ms = int(
            browser_cfg.get("timeout_seconds", 15.0) * 1000
        ) if "timeout_seconds" in browser_cfg else timeout_ms

        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None

    def _load_config(self) -> dict:
        """Safely reads config.json."""
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:  # noqa: BLE001
                logger.warning("Failed to load browser config: %s", e)
        return {}

    @classmethod
    def sanitize_and_validate_url(cls, raw_url: str) -> tuple[bool, str, Optional[str]]:
        """
        Validates URL scheme and normalizes web addresses.
        
        Returns:
            (is_safe, normalized_url, reason_if_blocked)
        """
        if not raw_url or not isinstance(raw_url, str):
            return False, "", "Empty or invalid URL provided."

        url = raw_url.strip()
        lower_url = url.lower()

        # Immediate check for blocked schemes before any scheme manipulation
        for blocked in cls.BLOCKED_SCHEMES:
            if lower_url.startswith(f"{blocked}:") or lower_url.startswith(f"{blocked}/"):
                return False, url, f"Blocked unsafe URL scheme: '{blocked}:'"

        # Handle scheme-less URLs (e.g. 'github.com/trending' -> 'https://github.com/trending')
        if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", url):
            url = f"https://{url}"

        try:
            parsed = urllib.parse.urlparse(url)
            scheme = (parsed.scheme or "").lower()

            if scheme in cls.BLOCKED_SCHEMES:
                return False, url, f"Blocked unsafe URL scheme: '{scheme}:'"

            if scheme not in cls.ALLOWED_SCHEMES:
                return False, url, f"Only HTTP/HTTPS protocols are permitted, got '{scheme}:'"

            if not parsed.netloc:
                return False, url, "URL is missing a valid host domain."

            # Block loopback / cloud metadata IP probing for security precaution
            hostname = (parsed.hostname or "").lower()
            if hostname in ("169.254.169.254", "metadata.google.internal"):
                return False, url, "Access to cloud metadata endpoints is prohibited."

            return True, url, None

        except Exception as e:  # noqa: BLE001
            return False, url, f"Malformed URL: {e}"

    def start(self) -> bool:
        """
        Idempotently starts the Playwright browser session.
        Recovers automatically if the browser was previously closed.
        """
        if self._page and not self._page.is_closed():
            return True

        try:
            from playwright.sync_api import sync_playwright

            if self._playwright is None:
                self._playwright = sync_playwright().start()

            # Launch Chromium (uses bundled or native channel)
            try:
                self._browser = self._playwright.chromium.launch(
                    headless=self.headless,
                    timeout=self.timeout_ms,
                )
            except Exception:
                # Fallback to pre-installed Edge / Chrome channel on Windows
                self._browser = self._playwright.chromium.launch(
                    channel="msedge",
                    headless=self.headless,
                    timeout=self.timeout_ms,
                )

            self._context = self._browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/125.0.0.0 Safari/537.36 Thanatos/1.0"
                ),
            )
            self._page = self._context.new_page()
            self._page.set_default_timeout(self.timeout_ms)
            logger.info("BrowserAgent initialized (headless=%s)", self.headless)
            return True

        except Exception as e:  # noqa: BLE001
            logger.error("Failed to launch Playwright browser: %s", e)
            self.close()
            return False

    def navigate(self, url: str) -> dict[str, Any]:
        """
        Core Primitive: Navigates to a target URL safely.
        """
        is_safe, clean_url, error_reason = self.sanitize_and_validate_url(url)
        if not is_safe:
            return {
                "success": False,
                "url": url,
                "title": "",
                "error": error_reason,
            }

        if not self.start():
            return {
                "success": False,
                "url": clean_url,
                "title": "",
                "error": "Could not launch browser instance.",
            }

        try:
            assert self._page is not None
            self._page.goto(clean_url, wait_until="domcontentloaded", timeout=self.timeout_ms)
            page_title = self._page.title()
            final_url = self._page.url
            return {
                "success": True,
                "url": final_url,
                "title": page_title,
                "error": None,
            }
        except Exception as e:  # noqa: BLE001
            logger.warning("Browser navigation error for %s: %s", clean_url, e)
            return {
                "success": False,
                "url": clean_url,
                "title": "",
                "error": str(e),
            }

    def search(self, query: str, engine: str = "duckduckgo") -> dict[str, Any]:
        """
        Core Primitive: Performs a web search directly inside the browser.
        Navigates and extracts organic result cards.
        """
        clean_query = query.strip()
        if not clean_query:
            return {"success": False, "results": [], "error": "Search query cannot be empty."}

        encoded = urllib.parse.quote_plus(clean_query)
        if engine.lower() == "google":
            search_url = f"https://www.google.com/search?q={encoded}"
        else:
            search_url = f"https://duckduckgo.com/?q={encoded}&ia=web"

        nav_result = self.navigate(search_url)
        if not nav_result["success"]:
            return {"success": False, "results": [], "error": nav_result["error"]}

        # Extract top search result links and snippets
        results = []
        try:
            assert self._page is not None
            # Wait for content to render
            self._page.wait_for_timeout(1000)

            # DuckDuckGo result elements
            articles = self._page.locator("article, [data-testid='result']").all()
            for art in articles[:5]:
                try:
                    title_elem = art.locator("h2, a[data-testid='result-title-a']").first
                    title = title_elem.inner_text().strip() if title_elem.count() > 0 else ""
                    link = title_elem.get_attribute("href") or ""
                    snippet_elem = art.locator("[data-result='snippet'], span").first
                    snippet = snippet_elem.inner_text().strip() if snippet_elem.count() > 0 else ""

                    if title:
                        results.append({"title": title, "link": link, "snippet": snippet})
                except Exception:
                    continue

            # Fallback if no specific cards found: extract visible link titles
            if not results:
                links = self._page.locator("h2 a, h3 a").all()
                for lnk in links[:5]:
                    t = lnk.inner_text().strip()
                    h = lnk.get_attribute("href") or ""
                    if t and len(t) > 3:
                        results.append({"title": t, "link": h, "snippet": ""})

            return {
                "success": True,
                "query": clean_query,
                "url": self._page.url,
                "title": self._page.title(),
                "results": results,
                "error": None,
            }
        except Exception as e:  # noqa: BLE001
            return {
                "success": False,
                "query": clean_query,
                "results": [],
                "error": f"Failed extracting search cards: {e}",
            }

    def click(self, selector_or_text: str) -> bool:
        """
        Core Primitive: Clicks an element by CSS selector, text content, or role.
        """
        if not self.start() or not self._page:
            return False

        target = selector_or_text.strip()
        try:
            # 1. Try direct selector
            locator = self._page.locator(target)
            if locator.count() > 0:
                locator.first.click(timeout=5000)
                return True

            # 2. Try by exact text or button role
            text_locator = self._page.get_by_text(target, exact=False)
            if text_locator.count() > 0:
                text_locator.first.click(timeout=5000)
                return True

            # 3. Try by role (button/link)
            btn_locator = self._page.get_by_role("button", name=target)
            if btn_locator.count() > 0:
                btn_locator.first.click(timeout=5000)
                return True

            return False
        except Exception as e:  # noqa: BLE001
            logger.warning("Click failed on '%s': %s", target, e)
            return False

    def type(
        self,
        text: str,
        selector: Optional[str] = None,
        clear: bool = False,
        press_enter: bool = False,
    ) -> bool:
        """
        Core Primitive: Types text into a specific selector or the currently active element.
        """
        if not self.start() or not self._page:
            return False

        try:
            if selector:
                loc = self._page.locator(selector).first
                if clear:
                    loc.fill("")
                loc.type(text)
                if press_enter:
                    loc.press("Enter")
            else:
                self._page.keyboard.type(text)
                if press_enter:
                    self._page.keyboard.press("Enter")
            return True
        except Exception as e:  # noqa: BLE001
            logger.warning("Type action failed: %s", e)
            return False

    def extract(self, selector: Optional[str] = None, max_length: int = 2500) -> dict[str, Any]:
        """
        Core Primitive: Extracts readable text, headings, and structure from the page.
        """
        if not self.start() or not self._page:
            return {"success": False, "title": "", "content": "", "error": "Browser not active."}

        try:
            title = self._page.title()
            current_url = self._page.url

            if selector:
                loc = self._page.locator(selector)
                if loc.count() > 0:
                    text_content = loc.first.inner_text().strip()
                else:
                    return {"success": False, "title": title, "content": "", "error": f"Selector '{selector}' not found."}
            else:
                # Intelligent content extraction: prioritize main/article before body
                text_content = ""
                for candidate in ("main", "article", "#content", ".content", "body"):
                    loc = self._page.locator(candidate)
                    if loc.count() > 0:
                        raw = str(loc.first.inner_text() or "").strip()
                        if raw:
                            text_content = raw
                            break
                if not text_content:
                    body_loc = self._page.locator("body")
                    if body_loc.count() > 0:
                        text_content = str(body_loc.first.inner_text() or "").strip()

            # Clean and trim excessive whitespace
            clean_text = re.sub(r"\n{3,}", "\n\n", text_content).strip()
            if len(clean_text) > max_length:
                clean_text = clean_text[:max_length] + "...\n[Content Truncated]"

            return {
                "success": True,
                "title": title,
                "url": current_url,
                "content": clean_text,
                "error": None,
            }
        except Exception as e:  # noqa: BLE001
            return {"success": False, "title": "", "content": "", "error": str(e)}

    def quick_browse(self, query_or_url: str) -> dict[str, Any]:
        """
        High-Level Recipe: Automatically determines whether input is a URL or search query,
        navigates or searches, and returns a structured summary card.
        """
        raw = query_or_url.strip()
        is_url = bool(
            re.match(r"^(https?://|[a-zA-Z0-9_\-]+\.[a-zA-Z]{2,})", raw)
            and not re.search(r"\s", raw)
        )

        if is_url:
            nav = self.navigate(raw)
            if not nav["success"]:
                return {"type": "navigate", "success": False, "summary": f"Failed to visit {raw}: {nav['error']}"}
            ext = self.extract(max_length=1500)
            summary = (
                f"Page Title: {nav['title']}\n"
                f"URL: {nav['url']}\n\n"
                f"Content Preview:\n{ext.get('content', 'No text content extracted.')}"
            )
            return {"type": "navigate", "success": True, "title": nav["title"], "url": nav["url"], "summary": summary}
        else:
            srch = self.search(raw)
            if not srch["success"]:
                return {"type": "search", "success": False, "summary": f"Search failed: {srch['error']}"}

            cards = srch.get("results", [])
            lines = [f"Search Results for: \"{raw}\" ({len(cards)} top hits)\n"]
            for idx, c in enumerate(cards, start=1):
                snip = f" - {c['snippet']}" if c.get('snippet') else ""
                lines.append(f"{idx}. {c['title']}\n   {c['link']}{snip}")

            summary = "\n".join(lines) if cards else f"No direct search cards found for '{raw}'."
            return {"type": "search", "success": True, "title": srch.get("title", ""), "url": srch.get("url", ""), "summary": summary}

    def close(self) -> None:
        """Closes page, browser context, and Playwright session cleanly."""
        try:
            if self._page and not self._page.is_closed():
                self._page.close()
        except Exception:  # noqa: BLE001
            pass
        finally:
            self._page = None

        try:
            if self._context:
                self._context.close()
        except Exception:  # noqa: BLE001
            pass
        finally:
            self._context = None

        try:
            if self._browser and self._browser.is_connected():
                self._browser.close()
        except Exception:  # noqa: BLE001
            pass
        finally:
            self._browser = None

        try:
            if self._playwright:
                self._playwright.stop()
        except Exception:  # noqa: BLE001
            pass
        finally:
            self._playwright = None

        logger.info("BrowserAgent shut down successfully.")

    def __enter__(self) -> BrowserAgent:
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
