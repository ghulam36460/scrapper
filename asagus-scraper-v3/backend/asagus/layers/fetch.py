from __future__ import annotations

import asyncio
import logging
import time

import httpx

from asagus.layers.browser import ChromiumBrowserPool
from asagus.layers.challenge_detector import ChallengeDetector
from asagus.layers.escalation import (
    EscalationLadder,
    EscalationStep,
    StepPlan,
    is_blocked,
)
from asagus.layers.external_adapters import ScraplingFetchAdapter
from asagus.layers.proxy import ProxyPoolManager
from asagus.layers.session_store import SessionStore
from asagus.models import FetchMode, FetchResult, PolicyDecision, ProxyEndpoint, ProxyTier, URLCandidate
from asagus.layers.social_auth import SocialAuthLayer

logger = logging.getLogger(__name__)

try:
    from curl_cffi.requests import AsyncSession as CurlAsyncSession
except ImportError:  # pragma: no cover - optional production dependency
    CurlAsyncSession = None


REALISTIC_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Upgrade-Insecure-Requests": "1",
}


class FetchLayer:
    """Static-first async fetcher with browser routing seam."""

    def __init__(
        self,
        enable_network_fetch: bool = False,
        proxy_manager: ProxyPoolManager | None = None,
        browser_pool: ChromiumBrowserPool | None = None,
        social_auth_layer: SocialAuthLayer | None = None,
        antibot_orchestrator=None,
        session_store: SessionStore | None = None,
        enable_escalation: bool = True,
        max_escalation_step: EscalationStep = EscalationStep.stealth_session,
    ) -> None:
        self.enable_network_fetch = enable_network_fetch
        self.proxy_manager = proxy_manager or ProxyPoolManager()
        self.browser_pool = browser_pool or ChromiumBrowserPool(pool_size=4)
        self.scrapling_fetch = ScraplingFetchAdapter()
        self.social_auth_layer = social_auth_layer
        self.antibot_orchestrator = antibot_orchestrator
        self.session_store = session_store
        self.enable_escalation = enable_escalation
        self.max_escalation_step = max_escalation_step
        self.challenge_detector = ChallengeDetector()

    async def close(self) -> None:
        await self.browser_pool.close()

    async def fetch(self, candidate: URLCandidate, decision: PolicyDecision) -> FetchResult:
        started = time.perf_counter()
        proxy = self.proxy_manager.choose(candidate, str(candidate.metadata.get("proxy_strategy", "auto")))
        social_auth = self.social_auth_layer.resolve(candidate.url) if self.social_auth_layer else None

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

        if social_auth and social_auth.enabled:
            candidate.metadata["social_auth"] = social_auth.public_payload()
            if social_auth.required and not social_auth.session_available:
                return FetchResult(
                    url=candidate.url,
                    final_url=candidate.url,
                    fetch_mode=FetchMode.dynamic,
                    proxy_used=proxy.id,
                    render_time_ms=int((time.perf_counter() - started) * 1000),
                    error=f"social_auth_session_missing:{social_auth.platform.value if social_auth.platform else 'unknown'}",
                )
            if social_auth.session_available:
                dynamic = await self._dynamic_placeholder(
                    candidate,
                    started,
                    proxy,
                    storage_state_path=social_auth.storage_state_path,
                )
                if dynamic.html and dynamic.status_code and dynamic.status_code < 500:
                    return dynamic
                if social_auth.required:
                    return dynamic

        if self.enable_escalation:
            return await self._fetch_with_escalation(candidate, decision, started)

        if decision.fetch_mode == FetchMode.dynamic:
            try:
                dynamic = await asyncio.wait_for(
                    self._dynamic_placeholder(candidate, started, proxy),
                    timeout=60,
                )
            except asyncio.TimeoutError:
                dynamic = FetchResult(
                    url=candidate.url,
                    fetch_mode=FetchMode.dynamic,
                    proxy_used=proxy.id,
                    render_time_ms=int((time.perf_counter() - started) * 1000),
                    error="browser_render_global_timeout_60s",
                )
            if dynamic.html and dynamic.status_code and dynamic.status_code < 500:
                return dynamic
            static = await self._static_fetch(candidate, started, proxy)
            if static.html:
                static.error = f"dynamic_fallback_to_static: {dynamic.error}".strip()
                return static
            return dynamic

        return await self._static_fetch(candidate, started, proxy)

    # ── Escalation ladder ────────────────────────────────────────────────

    async def _fetch_with_escalation(
        self,
        candidate: URLCandidate,
        decision: PolicyDecision,
        started: float,
    ) -> FetchResult:
        """Climb the avoidance ladder until a page is not blocked/challenged.

        Each rung is progressively stronger (static -> dynamic -> stealth ->
        stealth + reused session). On a successful stealth render we persist
        the clearance cookies so future requests to the same domain skip the
        challenge entirely.
        """
        stealth_available = self._stealth_available()
        has_saved_session = False
        if self.session_store is not None:
            has_saved_session = bool(await self.session_store.path_if_valid(candidate.url))

        # Start no lower than the policy's requested mode.
        start_step = EscalationStep.dynamic if decision.fetch_mode == FetchMode.dynamic else EscalationStep.static
        ladder = EscalationLadder(
            start_step=start_step,
            max_step=self.max_escalation_step,
            has_saved_session=has_saved_session,
            stealth_available=stealth_available,
        )

        last_result: FetchResult | None = None
        attempts: list[str] = []
        for plan in ladder:
            proxy = self._choose_proxy_for(candidate, plan.proxy_tier)
            result = await self._execute_step(candidate, decision, plan, started, proxy)
            challenge = self.challenge_detector.detect(
                result.html, result.status_code, final_url=result.final_url
            )
            blocked = is_blocked(result.status_code, bool(challenge.get("is_challenged")), result.html)
            attempts.append(f"{plan.label}:{result.status_code}:{'blocked' if blocked else 'ok'}")
            last_result = result

            if not blocked and result.html:
                if attempts:
                    result.error = (result.error + f" | escalation={','.join(attempts)}").strip(" |")
                logger.debug("Escalation succeeded for %s via %s", candidate.url, plan.label)
                return result

            logger.debug("Escalation step %s blocked for %s (status=%s)", plan.label, candidate.url, result.status_code)

        # Ladder exhausted: every rung was blocked.
        if last_result is None:
            last_result = FetchResult(
                url=candidate.url,
                fetch_mode=FetchMode.static,
                render_time_ms=int((time.perf_counter() - started) * 1000),
                error="escalation_no_attempts",
            )
        last_result.error = (
            f"escalation_exhausted_manual_review | {','.join(attempts)} | {last_result.error}"
        ).strip(" |")
        logger.info("Escalation exhausted for %s; flagged for manual review", candidate.url)
        return last_result

    def _stealth_available(self) -> bool:
        """True if any stealth browser engine is usable."""
        try:
            engines = self.browser_pool.available_engines()
        except Exception:
            return False
        return any(engines.get(name) for name in ("patchright", "camoufox", "nodriver"))

    def _choose_proxy_for(self, candidate: URLCandidate, tier: ProxyTier) -> ProxyEndpoint:
        """Pick a proxy for an escalation rung, honoring the job's strategy."""
        strategy = str(candidate.metadata.get("proxy_strategy", "auto"))
        if strategy in {"none"}:
            return self.proxy_manager.choose(candidate, strategy)
        # The ladder requests a specific tier; pass it as the strategy so the
        # proxy manager prefers that tier when an endpoint is configured.
        return self.proxy_manager.choose(candidate, tier.value)

    async def _execute_step(
        self,
        candidate: URLCandidate,
        decision: PolicyDecision,
        plan: StepPlan,
        started: float,
        proxy: ProxyEndpoint,
    ) -> FetchResult:
        """Run a single escalation rung and return its FetchResult."""
        if not plan.use_browser:
            return await self._static_fetch(candidate, started, proxy)

        engine = "auto" if plan.prefer_stealth_engine else "playwright"
        storage_state_path = ""
        if plan.use_saved_session and self.session_store is not None:
            storage_state_path = await self.session_store.path_if_valid(candidate.url)

        try:
            return await asyncio.wait_for(
                self._dynamic_placeholder(
                    candidate,
                    started,
                    proxy,
                    storage_state_path=storage_state_path,
                    engine_override=engine,
                    capture_session=plan.prefer_stealth_engine,
                ),
                timeout=60,
            )
        except asyncio.TimeoutError:
            return FetchResult(
                url=candidate.url,
                fetch_mode=FetchMode.dynamic,
                proxy_used=proxy.id,
                render_time_ms=int((time.perf_counter() - started) * 1000),
                error=f"browser_render_global_timeout_60s:{plan.label}",
            )

    async def _static_fetch(self, candidate: URLCandidate, started: float, proxy: ProxyEndpoint) -> FetchResult:
        if CurlAsyncSession is not None:
            result = await self._curl_cffi_fetch(candidate, started, proxy)
            if result.html and result.status_code and result.status_code < 400:
                return result
            if result.status_code in {403, 429, 503} or not result.html:
                scrapling = await self._scrapling_fetch(candidate, started, proxy, previous_error=result.error)
                if scrapling.html and scrapling.status_code and scrapling.status_code < 500:
                    return scrapling
            if result.status_code or result.html:
                return result

        scrapling = await self._scrapling_fetch(candidate, started, proxy)
        if scrapling.html and scrapling.status_code and scrapling.status_code < 500:
            return scrapling

        try:
            client_kwargs: dict[str, object] = {"timeout": 20, "follow_redirects": True}
            if proxy.endpoint:
                client_kwargs["proxy"] = proxy.endpoint
            async with httpx.AsyncClient(**client_kwargs) as client:
                response = await client.get(candidate.url, headers=REALISTIC_BROWSER_HEADERS)
            self.proxy_manager.register_result(proxy.id, success=response.status_code < 400, blocked=response.status_code in {403, 429})
            return FetchResult(
                url=candidate.url,
                status_code=response.status_code,
                final_url=str(response.url),
                content_type=response.headers.get("content-type", ""),
                html=response.text,
                markdown=response.text,
                fetch_mode=FetchMode.static,
                proxy_used=proxy.id,
                render_time_ms=int((time.perf_counter() - started) * 1000),
            )
        except Exception as exc:
            last_error = str(exc)
            self.proxy_manager.register_result(proxy.id, success=False, error=last_error)
            return FetchResult(
                url=candidate.url,
                fetch_mode=FetchMode.static,
                proxy_used=proxy.id,
                render_time_ms=int((time.perf_counter() - started) * 1000),
                error=last_error,
            )

    async def _scrapling_fetch(
        self,
        candidate: URLCandidate,
        started: float,
        proxy: ProxyEndpoint,
        previous_error: str = "",
    ) -> FetchResult:
        if not self.scrapling_fetch.available:
            return FetchResult(
                url=candidate.url,
                fetch_mode=FetchMode.static,
                proxy_used=proxy.id,
                render_time_ms=int((time.perf_counter() - started) * 1000),
                error="scrapling_not_available",
            )
        result = await self.scrapling_fetch.fetch(candidate, started, proxy)
        self.proxy_manager.register_result(
            proxy.id,
            success=bool(result.status_code and result.status_code < 400),
            blocked=result.status_code in {403, 429},
            error=result.error if result.status_code >= 400 else "",
        )
        if previous_error:
            result.error = f"{result.error}; previous={previous_error}".strip("; ")
        return result

    async def _curl_cffi_fetch(self, candidate: URLCandidate, started: float, proxy: ProxyEndpoint) -> FetchResult:
        session = None
        try:
            kwargs: dict[str, object] = {
                "impersonate": "chrome124",
                "timeout": 20,
                "headers": REALISTIC_BROWSER_HEADERS,
            }
            if proxy.endpoint:
                kwargs["proxies"] = {"http": proxy.endpoint, "https": proxy.endpoint}
            session = CurlAsyncSession(**kwargs)
            response = await session.get(candidate.url, allow_redirects=True)
            self.proxy_manager.register_result(proxy.id, success=response.status_code < 400, blocked=response.status_code in {403, 429})
            return FetchResult(
                url=candidate.url,
                status_code=response.status_code,
                final_url=str(response.url),
                content_type=response.headers.get("content-type", ""),
                html=response.text,
                markdown=response.text,
                fetch_mode=FetchMode.static,
                proxy_used=proxy.id,
                render_time_ms=int((time.perf_counter() - started) * 1000),
            )
        except Exception as exc:
            self.proxy_manager.register_result(proxy.id, success=False, error=str(exc))
            return FetchResult(
                url=candidate.url,
                fetch_mode=FetchMode.static,
                proxy_used=proxy.id,
                render_time_ms=int((time.perf_counter() - started) * 1000),
                error=f"curl_cffi_failed: {exc}",
            )
        finally:
            if session is not None:
                try:
                    close = getattr(session, "close", None)
                    if close:
                        maybe_awaitable = close()
                        if hasattr(maybe_awaitable, "__await__"):
                            await maybe_awaitable
                except Exception:
                    pass  # Suppress cleanup errors

    async def _dynamic_placeholder(
        self,
        candidate: URLCandidate,
        started: float,
        proxy: ProxyEndpoint,
        storage_state_path: str = "",
        engine_override: str = "",
        capture_session: bool = False,
    ) -> FetchResult:
        try:
            html, status_final, session_state = await self.browser_pool.render_with_session(
                candidate.url,
                proxy_url=proxy.endpoint,
                storage_state_path=storage_state_path,
                engine_override=engine_override,
                capture_session=capture_session,
            )
            # Robust parsing: format is "status_code:final_url"
            if ":" in status_final:
                status_text, final_url = status_final.split(":", 1)
            else:
                status_text = status_final
                final_url = candidate.url
            try:
                status_code = int(status_text)
            except (ValueError, TypeError):
                status_code = 200
            self.proxy_manager.register_result(proxy.id, success=status_code < 400, blocked=status_code in {403, 429})
            # Persist a cleared session for reuse on this domain.
            if (
                capture_session
                and session_state
                and status_code < 400
                and self.session_store is not None
            ):
                await self.session_store.save(candidate.url, session_state)
            return FetchResult(
                url=candidate.url,
                status_code=status_code,
                final_url=final_url,
                content_type="text/html",
                html=html,
                markdown=html,
                fetch_mode=FetchMode.dynamic,
                proxy_used=proxy.id,
                render_time_ms=int((time.perf_counter() - started) * 1000),
            )
        except Exception as exc:
            self.proxy_manager.register_result(proxy.id, success=False, error=str(exc))
            return FetchResult(
                url=candidate.url,
                final_url=candidate.url,
                fetch_mode=FetchMode.dynamic,
                proxy_used=proxy.id,
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
