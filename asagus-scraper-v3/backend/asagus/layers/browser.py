from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator


class ChromiumBrowserPool:
    """Playwright Chromium renderer for dynamic pages, without challenge bypass."""

    def __init__(self, pool_size: int = 4, timeout_ms: int = 30_000) -> None:
        self.pool_size = max(1, pool_size)
        self.timeout_ms = timeout_ms
        self._semaphore = asyncio.Semaphore(self.pool_size)
        self._playwright = None
        self._browser = None

    async def render(self, url: str) -> tuple[str, str]:
        async with self._semaphore:
            async with self._page() as page:
                response = await page.goto(url, wait_until="domcontentloaded", timeout=self.timeout_ms)
                await page.wait_for_load_state("networkidle", timeout=min(self.timeout_ms, 10_000))
                html = await page.content()
                final_url = page.url
                status = response.status if response else 0
                return html, f"{status}:{final_url}"

    async def close(self) -> None:
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

    @asynccontextmanager
    async def _page(self) -> AsyncIterator[object]:
        browser = await self._get_browser()
        context = await browser.new_context(
            user_agent="ASAGUSBot/3.0 (+respectful research crawler)",
            viewport={"width": 1365, "height": 900},
            java_script_enabled=True,
        )
        page = await context.new_page()
        try:
            yield page
        finally:
            await context.close()

    async def _get_browser(self) -> object:
        if self._browser:
            return self._browser
        from playwright.async_api import async_playwright  # type: ignore

        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=True)
        return self._browser

    def state(self) -> dict[str, object]:
        return {
            "engine": "playwright.chromium",
            "pool_size": self.pool_size,
            "timeout_ms": self.timeout_ms,
            "challenge_bypass": False,
            "purpose": "render JavaScript pages when policy/compliance allow dynamic fetch",
        }
