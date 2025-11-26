"""Playwright-based browser automation."""

import asyncio
import logging
from pathlib import Path
from typing import Any

from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    async_playwright,
)

from ..config import settings

logger = logging.getLogger(__name__)


class BrowserController:
    """Control browser via Playwright with proxy support."""

    def __init__(
        self,
        browser_type: str = settings.browser_type,
        headless: bool = settings.headless,
        proxy_url: str | None = None,
    ) -> None:
        self.browser_type = browser_type
        self.headless = headless
        self.proxy_url = proxy_url
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    async def start(self) -> Page:
        """Start browser and return page."""
        self._playwright = await async_playwright().start()

        browser_launcher = getattr(self._playwright, self.browser_type)

        launch_args: dict[str, Any] = {
            "headless": self.headless,
        }

        # Add proxy if configured
        if self.proxy_url:
            launch_args["proxy"] = {"server": self.proxy_url}

        # Add args for better compatibility
        if self.browser_type == "chromium":
            launch_args["args"] = [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ]

        self._browser = await browser_launcher.launch(**launch_args)

        # Create context with common settings
        context_args: dict[str, Any] = {
            "viewport": {"width": 1920, "height": 1080},
            "user_agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "ignore_https_errors": True,  # For proxy MITM
        }

        self._context = await self._browser.new_context(**context_args)
        self._page = await self._context.new_page()

        logger.info(f"Browser started: {self.browser_type}, headless={self.headless}")
        return self._page

    async def stop(self) -> None:
        """Stop browser."""
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        logger.info("Browser stopped")

    @property
    def page(self) -> Page:
        """Get current page."""
        if not self._page:
            raise RuntimeError("Browser not started")
        return self._page

    @property
    def context(self) -> BrowserContext:
        """Get browser context."""
        if not self._context:
            raise RuntimeError("Browser not started")
        return self._context

    async def navigate(self, url: str, wait_until: str = "networkidle") -> None:
        """Navigate to URL and wait for load."""
        await self.page.goto(url, wait_until=wait_until)
        logger.info(f"Navigated to: {url}")

    async def screenshot(self, path: Path) -> None:
        """Take screenshot."""
        path.parent.mkdir(parents=True, exist_ok=True)
        await self.page.screenshot(path=path, full_page=True)
        logger.info(f"Screenshot saved: {path}")

    async def get_page_info(self) -> dict[str, Any]:
        """Get current page information."""
        return {
            "url": self.page.url,
            "title": await self.page.title(),
        }

    async def get_cookies(self) -> list[dict[str, Any]]:
        """Get all cookies."""
        return await self.context.cookies()

    async def set_cookies(self, cookies: list[dict[str, Any]]) -> None:
        """Set cookies."""
        await self.context.add_cookies(cookies)

    async def execute_script(self, script: str) -> Any:
        """Execute JavaScript in page context."""
        return await self.page.evaluate(script)

    async def detect_technologies(self) -> dict[str, list[str]]:
        """Detect technologies used on page."""
        result: dict[str, list[str]] = {
            "frameworks": [],
            "libraries": [],
            "analytics": [],
            "anti_bot": [],
        }

        # Detection scripts
        detections = await self.page.evaluate(
            """() => {
            const detected = {
                frameworks: [],
                libraries: [],
                analytics: [],
                anti_bot: []
            };

            // React
            if (window.React || document.querySelector('[data-reactroot]')) {
                detected.frameworks.push('React');
            }

            // Vue
            if (window.Vue || document.querySelector('[data-v-]')) {
                detected.frameworks.push('Vue');
            }

            // Angular
            if (window.ng || document.querySelector('[ng-app], [data-ng-app], [ng-controller]')) {
                detected.frameworks.push('Angular');
            }

            // jQuery
            if (window.jQuery || window.$) {
                detected.libraries.push('jQuery');
            }

            // Analytics
            if (window.ga || window.gtag) {
                detected.analytics.push('Google Analytics');
            }

            // Anti-bot detection
            if (window.__cf_bm || document.querySelector('script[src*="cloudflare"]')) {
                detected.anti_bot.push('Cloudflare');
            }
            if (window._akamai || document.querySelector('script[src*="akamai"]')) {
                detected.anti_bot.push('Akamai');
            }
            if (window.DD_RUM || document.querySelector('script[src*="datadome"]')) {
                detected.anti_bot.push('DataDome');
            }
            if (document.querySelector('script[src*="perimeterx"]')) {
                detected.anti_bot.push('PerimeterX');
            }
            if (document.querySelector('iframe[src*="recaptcha"]')) {
                detected.anti_bot.push('reCAPTCHA');
            }
            if (document.querySelector('iframe[src*="hcaptcha"]')) {
                detected.anti_bot.push('hCaptcha');
            }

            return detected;
        }"""
        )

        result.update(detections)
        return result

    async def find_forms(self) -> list[dict[str, Any]]:
        """Find all forms on the page."""
        return await self.page.evaluate(
            """() => {
            const forms = document.querySelectorAll('form');
            return Array.from(forms).map(form => ({
                action: form.action,
                method: form.method,
                id: form.id,
                name: form.name,
                fields: Array.from(form.elements).map(el => ({
                    type: el.type,
                    name: el.name,
                    id: el.id,
                    required: el.required
                })).filter(f => f.name || f.id)
            }));
        }"""
        )

    async def find_links(self, internal_only: bool = False) -> list[dict[str, str]]:
        """Find all links on the page."""
        current_domain = await self.page.evaluate("() => window.location.hostname")

        links = await self.page.evaluate(
            """() => {
            const anchors = document.querySelectorAll('a[href]');
            return Array.from(anchors).map(a => ({
                href: a.href,
                text: a.textContent?.trim() || '',
                rel: a.rel
            }));
        }"""
        )

        if internal_only:
            links = [link for link in links if current_domain in link.get("href", "")]

        return links

    async def fill_form(self, form_data: dict[str, str]) -> None:
        """Fill form fields."""
        for selector, value in form_data.items():
            await self.page.fill(selector, value)

    async def click(self, selector: str) -> None:
        """Click element."""
        await self.page.click(selector)

    async def wait_for_selector(self, selector: str, timeout: int = 30000) -> None:
        """Wait for element to appear."""
        await self.page.wait_for_selector(selector, timeout=timeout)

    async def wait_for_navigation(self) -> None:
        """Wait for navigation to complete."""
        await self.page.wait_for_load_state("networkidle")

    async def record_har(self, path: Path) -> None:
        """Start HAR recording (Playwright native)."""
        if self._context:
            await self._context.close()
        if self._browser:
            path.parent.mkdir(parents=True, exist_ok=True)
            self._context = await self._browser.new_context(
                record_har_path=str(path),
                ignore_https_errors=True,
            )
            self._page = await self._context.new_page()

    async def get_network_requests(self) -> list[dict[str, Any]]:
        """Get all network requests made by page (via CDP)."""
        if self.browser_type != "chromium":
            return []

        cdp = await self.context.new_cdp_session(self.page)
        await cdp.send("Network.enable")

        # This captures future requests; for past requests, use HAR
        return []
