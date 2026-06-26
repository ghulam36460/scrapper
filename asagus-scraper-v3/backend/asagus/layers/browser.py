from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator, Literal

REALISTIC_BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

BrowserEngine = Literal["playwright", "patchright", "camoufox", "nodriver", "auto"]
logger = logging.getLogger(__name__)


class ChromiumBrowserPool:
    """Playwright Chromium renderer for dynamic pages, without challenge bypass."""

    def __init__(
        self,
        pool_size: int = 4,
        timeout_ms: int = 30_000,
        engine: BrowserEngine = "playwright",
        headless: bool = True,
        camoufox_binary_path: str = "",
    ) -> None:
        self.pool_size = max(1, pool_size)
        self.timeout_ms = timeout_ms
        self.engine = engine
        self.headless = headless
        self.camoufox_binary_path = camoufox_binary_path
        self._semaphore = asyncio.Semaphore(self.pool_size)
        self._playwright = None
        self._browser = None

    async def render(self, url: str, proxy_url: str = "", storage_state_path: str = "") -> tuple[str, str]:
        html, status_final, _ = await self.render_with_session(
            url, proxy_url=proxy_url, storage_state_path=storage_state_path
        )
        return html, status_final

    async def render_with_session(
        self,
        url: str,
        proxy_url: str = "",
        storage_state_path: str = "",
        capture_session: bool = False,
        engine_override: str = "",
    ) -> tuple[str, str, dict | None]:
        """Render a page and optionally capture the resulting session state.

        Returns ``(html, "status:final_url", storage_state | None)``. The
        storage_state is only captured for the Playwright path (the engine
        that exposes ``context.storage_state()``); stealth engines return
        ``None`` for it and rely on their own session handling.

        ``engine_override`` lets a caller (e.g. the escalation ladder) pick a
        specific engine for this single render without mutating pool state.
        """
        effective_engine = engine_override or self.engine
        async with self._semaphore:
            # Stealth engines cannot consume a Playwright storage_state file,
            # so a saved session forces the Playwright path.
            if effective_engine != "playwright" and not storage_state_path:
                rendered = await self._render_with_selected_engine(
                    url, proxy_url=proxy_url, engine=effective_engine
                )
                if rendered is not None:
                    return rendered[0], rendered[1], None
            elif storage_state_path and effective_engine != "playwright":
                logger.info("Using Playwright Chromium for storage-state session rendering")

            async with self._page(proxy_url=proxy_url, storage_state_path=storage_state_path) as page:
                response = await page.goto(url, wait_until="domcontentloaded", timeout=self.timeout_ms)
                await page.wait_for_load_state("networkidle", timeout=min(self.timeout_ms, 10_000))
                html = await page.content()
                final_url = page.url
                status = response.status if response else 0
                session_state: dict | None = None
                if capture_session:
                    try:
                        session_state = await page.context.storage_state()
                    except Exception as exc:  # pragma: no cover - defensive
                        logger.debug("Could not capture storage_state for %s: %s", url, exc)
                return html, f"{status}:{final_url}", session_state

    async def close(self) -> None:
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

    async def _render_with_selected_engine(
        self, url: str, proxy_url: str = "", engine: str = ""
    ) -> tuple[str, str] | None:
        selected = engine or self.engine
        engines: list[str]
        if selected == "auto":
            engines = ["camoufox", "patchright", "nodriver"]
        else:
            engines = [selected]

        for engine in engines:
            try:
                if engine == "patchright":
                    rendered = await self._render_with_patchright(url, proxy_url)
                elif engine == "camoufox":
                    rendered = await self._render_with_camoufox(url, proxy_url)
                elif engine == "nodriver":
                    rendered = await self._render_with_nodriver(url, proxy_url)
                else:
                    rendered = None
            except Exception as exc:
                logger.warning("%s render failed, falling back if possible: %s", engine, exc)
                logger.debug("%s traceback:", engine, exc_info=True)
                rendered = None

            if rendered is not None:
                return rendered

        logger.warning("Browser engine %s unavailable; falling back to Playwright Chromium", selected)
        return None

    async def _render_with_patchright(self, url: str, proxy_url: str = "") -> tuple[str, str] | None:
        from asagus.layers.patchright_integration import PatchrightBrowser, PatchrightConfig, is_patchright_available

        if not is_patchright_available():
            return None

        browser = PatchrightBrowser(
            PatchrightConfig(
                headless=self.headless,
                proxy_server=proxy_url or None,
                timeout=self.timeout_ms,
            )
        )
        if not await browser.start():
            return None
        try:
            success, html = await browser.navigate(url)
            if not success:
                return None
            return html, self._navigation_status_final(browser, url)
        finally:
            await browser.close()

    async def _render_with_camoufox(self, url: str, proxy_url: str = "") -> tuple[str, str] | None:
        from asagus.layers.camoufox_integration import CamoufoxBrowser, CamoufoxCustomConfig, is_camoufox_available

        if not is_camoufox_available():
            return None

        browser = CamoufoxBrowser(
            CamoufoxCustomConfig(
                camoufox_binary_path=self.camoufox_binary_path or None,
                headless=self.headless,
                proxy_server=proxy_url or None,
                timeout=self.timeout_ms,
            )
        )
        if not await browser.start():
            return None
        try:
            success, html = await browser.navigate(url)
            if not success:
                return None
            return html, self._navigation_status_final(browser, url)
        finally:
            await browser.close()

    async def _render_with_nodriver(self, url: str, proxy_url: str = "") -> tuple[str, str] | None:
        from asagus.layers.nodriver_integration import NoDriverBrowser, NoDriverConfig, is_nodriver_available

        if not is_nodriver_available():
            return None

        browser = NoDriverBrowser(
            NoDriverConfig(
                headless=self.headless,
                proxy_server=proxy_url or None,
                page_load_timeout=max(1, self.timeout_ms // 1000),
            )
        )
        if not await browser.start():
            return None
        try:
            success, html = await browser.navigate(url)
            if not success:
                return None
            return html, self._navigation_status_final(browser, url)
        finally:
            await browser.close()

    def _navigation_status_final(self, browser: object, requested_url: str) -> str:
        status_raw = getattr(browser, "last_status_code", 200)
        try:
            status = int(status_raw)
        except (TypeError, ValueError):
            status = 200
        final_url = str(getattr(browser, "last_final_url", "") or requested_url)
        return f"{status}:{final_url}"

    @asynccontextmanager
    async def _page(self, proxy_url: str = "", storage_state_path: str = "") -> AsyncIterator[object]:
        browser = await self._get_browser()
        context_options: dict[str, object] = {
            "user_agent": REALISTIC_BROWSER_USER_AGENT,
            "viewport": {"width": 1365, "height": 900},
            "java_script_enabled": True,
            "locale": "en-US",
            "timezone_id": "America/New_York",
        }
        if proxy_url:
            context_options["proxy"] = {"server": proxy_url}
        if storage_state_path:
            context_options["storage_state"] = storage_state_path
        context = await browser.new_context(**context_options)
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
        self._browser = await self._playwright.chromium.launch(headless=self.headless)
        return self._browser

    def state(self) -> dict[str, object]:
        return {
            "engine": self.engine if self.engine != "playwright" else "playwright.chromium",
            "pool_size": self.pool_size,
            "timeout_ms": self.timeout_ms,
            "headless": self.headless,
            "camoufox_binary_path": self.camoufox_binary_path,
            "challenge_bypass": False,
            "storage_state_sessions": "playwright_context_capture_and_reuse",
            "available_engines": self.available_engines(),
            "purpose": "render JavaScript pages when policy/compliance allow dynamic fetch",
        }

    def available_engines(self) -> dict[str, bool]:
        availability = {"playwright": True}

        try:
            from asagus.layers.patchright_integration import is_patchright_available
            availability["patchright"] = is_patchright_available()
        except Exception:
            availability["patchright"] = False

        try:
            from asagus.layers.camoufox_integration import is_camoufox_available
            availability["camoufox"] = is_camoufox_available()
        except Exception:
            availability["camoufox"] = False

        try:
            from asagus.layers.nodriver_integration import is_nodriver_available
            availability["nodriver"] = is_nodriver_available()
        except Exception:
            availability["nodriver"] = False

        return availability
