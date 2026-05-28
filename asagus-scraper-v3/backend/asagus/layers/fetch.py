from __future__ import annotations

import time

import httpx

from asagus.layers.browser import ChromiumBrowserPool
from asagus.layers.proxy import ProxyPoolManager
from asagus.models import FetchMode, FetchResult, PolicyDecision, URLCandidate


class FetchLayer:
    """Static-first async fetcher with browser routing seam."""

    def __init__(
        self,
        enable_network_fetch: bool = False,
        proxy_manager: ProxyPoolManager | None = None,
        browser_pool: ChromiumBrowserPool | None = None,
    ) -> None:
        self.enable_network_fetch = enable_network_fetch
        self.proxy_manager = proxy_manager or ProxyPoolManager()
        self.browser_pool = browser_pool or ChromiumBrowserPool(pool_size=4)

    async def fetch(self, candidate: URLCandidate, decision: PolicyDecision) -> FetchResult:
        started = time.perf_counter()
        proxy = self.proxy_manager.choose(candidate, str(candidate.metadata.get("proxy_strategy", "auto")))

        if not self.enable_network_fetch:
            html = self._offline_preview(candidate)
            self.proxy_manager.register_result(proxy.id, success=True)
            return FetchResult(
                url=candidate.url,
                status_code=200,
                final_url=candidate.url,
                content_type="text/html",
                html=html,
                markdown=html,
                fetch_mode=decision.fetch_mode,
                proxy_used=proxy.id,
                error="offline_preview_only",
                render_time_ms=int((time.perf_counter() - started) * 1000),
            )

        if decision.fetch_mode == FetchMode.dynamic:
            dynamic = await self._dynamic_placeholder(candidate, started, proxy.id)
            if dynamic.html and dynamic.status_code and dynamic.status_code < 500:
                return dynamic
            static = await self._static_fetch(candidate, started, proxy.id)
            if static.html:
                static.error = f"dynamic_fallback_to_static: {dynamic.error}".strip()
                return static
            return dynamic

        return await self._static_fetch(candidate, started, proxy.id)

    async def _static_fetch(self, candidate: URLCandidate, started: float, proxy_id: str) -> FetchResult:
        headers = [
            {"User-Agent": "ASAGUSBot/3.0 (+respectful business contact crawler)"},
            {
                "User-Agent": "Mozilla/5.0 (compatible; ASAGUSBot/3.0; +https://localhost)",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
        ]
        last_error = ""
        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                response = None
                for header in headers:
                    response = await client.get(candidate.url, headers=header)
                    if response.status_code < 500 or response.status_code in {403, 404, 429}:
                        break
                if response is None:
                    raise RuntimeError("no response")
            self.proxy_manager.register_result(proxy_id, success=response.status_code < 400, blocked=response.status_code in {403, 429})
            return FetchResult(
                url=candidate.url,
                status_code=response.status_code,
                final_url=str(response.url),
                content_type=response.headers.get("content-type", ""),
                html=response.text,
                markdown=response.text,
                fetch_mode=FetchMode.static,
                proxy_used=proxy_id,
                render_time_ms=int((time.perf_counter() - started) * 1000),
            )
        except Exception as exc:
            last_error = str(exc)
            self.proxy_manager.register_result(proxy_id, success=False, error=last_error)
            return FetchResult(
                url=candidate.url,
                fetch_mode=FetchMode.static,
                proxy_used=proxy_id,
                render_time_ms=int((time.perf_counter() - started) * 1000),
                error=last_error,
            )

    async def _dynamic_placeholder(self, candidate: URLCandidate, started: float, proxy_id: str) -> FetchResult:
        try:
            html, status_final = await self.browser_pool.render(candidate.url)
            status_text, final_url = status_final.split(":", 1)
            status_code = int(status_text)
            self.proxy_manager.register_result(proxy_id, success=status_code < 400, blocked=status_code in {403, 429})
            return FetchResult(
                url=candidate.url,
                status_code=status_code,
                final_url=final_url,
                content_type="text/html",
                html=html,
                markdown=html,
                fetch_mode=FetchMode.dynamic,
                proxy_used=proxy_id,
                render_time_ms=int((time.perf_counter() - started) * 1000),
            )
        except Exception as exc:
            self.proxy_manager.register_result(proxy_id, success=False, error=str(exc))
            return FetchResult(
                url=candidate.url,
                final_url=candidate.url,
                fetch_mode=FetchMode.dynamic,
                proxy_used=proxy_id,
                render_time_ms=int((time.perf_counter() - started) * 1000),
                error=f"chromium_render_failed: {exc}",
            )

    def _offline_preview(self, candidate: URLCandidate) -> str:
        query = candidate.metadata.get("query", "business")
        location = candidate.metadata.get("location", "")
        return (
            "<html><body>"
            f"<h1>{query.title()} leads in {location.title()}</h1>"
            "<article data-business>"
            f"<h2>{query.title()} Sample Business</h2>"
            "<p>Offline preview only. Enable real network fetch and search discovery to collect public business contacts.</p>"
            f"<p>{location} main market</p>"
            "</article>"
            "</body></html>"
        )
