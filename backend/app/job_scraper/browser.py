"""Playwright-backed LinkedIn search-results fetcher.

The ONLY part of the scraper that touches a real browser. Everything else —
card detection, per-card parsing, dedup, date validation, persistence — is
browser-free and unit-tested without Playwright.

No LinkedIn credentials are required: LinkedIn serves guest job-search
results. We launch headless Chromium, navigate to the search URL, dismiss
the (optional) guest login-wall prompt, scroll a bounded number of times to
trigger the infinite scroll, and return the rendered HTML. Failures raise
typed LinkedInScraperError subclasses so the API can return a helpful error
instead of crashing.

Playwright is imported lazily so the rest of the app and the unit tests
never need the package (or its browsers) installed.
"""

import logging
from contextlib import contextmanager

from app.config.settings import get_settings

logger = logging.getLogger(__name__)


class LinkedInScraperError(Exception):
    """Base error for the LinkedIn search scraper."""


class BrowserLaunchError(LinkedInScraperError):
    """Could not launch Chromium (Playwright not installed / no browser)."""


class LinkedInUnavailableError(LinkedInScraperError):
    """LinkedIn was unreachable or returned an HTTP error."""


class AccessBlockedError(LinkedInScraperError):
    """LinkedIn redirected to a login / rate-limit wall — triggering it
    would need credentials or a wait; we stop and report cleanly."""


class LinkedInSearchBrowser:
    """Fetches the rendered HTML of a LinkedIn job-search page."""

    def __init__(
        self,
        *,
        headless: bool | None = None,
        timeout_seconds: float | None = None,
        max_scroll_passes: int | None = None,
    ) -> None:
        settings = get_settings()
        self._headless = settings.scraper_headless if headless is None else headless
        self._timeout_ms = int(
            (settings.scraper_navigation_timeout_seconds if timeout_seconds is None else timeout_seconds)
            * 1000
        )
        self._max_scrolls = (
            settings.scraper_max_scroll_passes if max_scroll_passes is None else max_scroll_passes
        )

    def fetch_search_html(self, url: str) -> str:
        """Opens `url` in a headless browser, scrolls a bounded amount, and
        returns the rendered page HTML. Raises a LinkedInScraperError
        subclass on browser/unavailable/login/rate-limit failures."""
        with self._browser_session() as (browser, page):
            try:
                response = page.goto(url, wait_until="domcontentloaded", timeout=self._timeout_ms)
            except Exception as exc:  # pragma: no cover - raised by Playwright timeout
                raise LinkedInUnavailableError(
                    f"LinkedIn did not respond within {self._timeout_ms / 1000:.0f}s."
                ) from exc
            if response is None:
                raise LinkedInUnavailableError("LinkedIn returned no response.")
            if response.status >= 400:
                raise LinkedInUnavailableError(f"LinkedIn returned HTTP {response.status}.")

            self._dismiss_guest_prompt(page)

            for _ in range(self._max_scrolls):
                page.mouse.wheel(0, 1500)
                page.wait_for_timeout(900)

            final_url = page.url
            html = page.content()

        self._validate_page(final_url, html)
        return html

    def fetch_job_details_html(self, url: str) -> str:
        """Fetches a single LinkedIn job detail page for relevance fallback."""
        with self._browser_session() as (browser, page):
            try:
                response = page.goto(url, wait_until="domcontentloaded", timeout=self._timeout_ms)
            except Exception as exc:  # pragma: no cover - raised by Playwright timeout
                raise LinkedInUnavailableError(
                    f"LinkedIn detail page did not respond within {self._timeout_ms / 1000:.0f}s."
                ) from exc
            if response is None:
                raise LinkedInUnavailableError("LinkedIn detail page returned no response.")
            if response.status >= 400:
                raise LinkedInUnavailableError(f"LinkedIn detail page returned HTTP {response.status}.")
            self._dismiss_guest_prompt(page)
            final_url = page.url
            html = page.content()

        self._validate_page(final_url, html)
        return html

    @contextmanager
    def _browser_session(self):
        """Context manager for browser creation/cleanup used by search and detail loads."""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:  # pragma: no cover - depends on install
            raise BrowserLaunchError(
                "Playwright is not installed. Run 'pip install playwright && "
                "playwright install chromium' on the backend."
            ) from exc

        browser = None
        page = None
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=self._headless,
                    args=["--disable-blink-features=AutomationControlled"],
                )
                page = browser.new_page(viewport={"width": 1280, "height": 900})
                yield browser, page
        except Exception as exc:  # pragma: no cover - unexpected browser error
            logger.exception("Unexpected LinkedIn scraper failure")
            raise LinkedInScraperError(f"Unexpected LinkedIn scraper failure: {exc}") from exc
        finally:
            if page is not None:
                try:
                    page.close()
                except Exception:
                    pass
            if browser is not None:
                try:
                    browser.close()
                except Exception:
                    pass

    @staticmethod
    def _dismiss_guest_prompt(page) -> None:
        """Closes LinkedIn's guest "Sign in to see this" modal if it appears,
        so the job cards remain visible."""
        for selector in ("button[aria-label='Dismiss']", "button[aria-label='Close']", "button.modal__dismiss"):
            try:
                page.wait_for_selector(selector, state="visible", timeout=2000)
                page.locator(selector).first.click(timeout=2000)
                return
            except Exception:
                continue

    @staticmethod
    def _validate_page(final_url: str, html: str) -> None:
        if any(marker in final_url for marker in ("/authwall", "/m/login", "/login")):
            raise AccessBlockedError(
                "LinkedIn redirected the search to a login/rate-limit wall. "
                "New jobs are still returned by guest search; wait a moment and retry."
            )
        lowered = html.lower()
        if "you've been temporarily blocked" in lowered or "too many requests" in lowered:
            raise AccessBlockedError("LinkedIn has temporarily rate-limited this client. Retry later.")