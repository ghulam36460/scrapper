from __future__ import annotations

import asyncio
import logging
import os
import sys
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

# Force WindowsSelectorEventLoopPolicy on Windows for subprocess compatibility
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from asagus import __version__
from asagus.config import Settings, get_settings
from asagus.logging_config import configure_logging
from asagus.layers.antibot_orchestrator import AntiBotConfig, AntiBotOrchestrator
from asagus.layers.antibot_layer2_stealth import StealthApproach
from asagus.layers.antibot_layer3_tls import BrowserTLSFingerprint
from asagus.layers.browser import ChromiumBrowserPool
from asagus.layers.compliance import ComplianceLayer
from asagus.layers.crawl_control import CrawlControlPlane
from asagus.layers.discovery import SearchDiscoveryLayer
from asagus.layers.dom_tools import DOMTools
from asagus.layers.escalation import EscalationStep
from asagus.layers.session_store import SessionStore
from asagus.layers.enrichment import EnrichmentLayer
from asagus.layers.extraction import (
    ExtractionLayer,
    should_skip_url,
    normalize_phone,
)
from asagus.layers.fetch import FetchLayer
from asagus.layers.graph import GraphRelationshipEngine
from asagus.layers.indexing import IndexingLayer
from asagus.layers.noise_reduction import clean_record_fields
from asagus.layers.nlp_intelligence import NLPIntelligenceLayer
from asagus.layers.policy import PolicyEngine
from asagus.layers.proxy import ProxyPoolManager
from asagus.layers.retrieval import RetrievalLayer
from asagus.layers.social_auth import SocialAuthLayer
from asagus.layers.storage import StorageLayer
from asagus.layers.throughput import resource_profile_for
from asagus.llm.providers import LLMClient
from asagus.models import (
    JobStatus,
    LayerName,
    LLMProvider,
    MDPAction,
    PolicyFeedback,
    SearchDiscoveryRequest,
    ScrapeJob,
    ScrapeStartRequest,
    URLCandidate,
    utc_now,
)
from asagus.services.llm_settings import hydrate_runtime_llm
from asagus.services.runtime import runtime
from asagus.routers.deps import get_llm_client
from asagus.services.job_helpers import (
    antibot_preset_plan,
    candidate_partial_record,
    discovery_refill as _discovery_refill,
    effective_website_filter,
    effective_runtime_flags,
    emit,
    merge_candidate_partial_record,
    mode_plan,
    planned_page_count,
    partial_record,
    proxy_urls_from_settings,
    sleep_or_cancel,
    useful_record,
    website_filter_allows,
)

logger = logging.getLogger(__name__)


@dataclass
class AppServices:
    policy: PolicyEngine
    crawl: CrawlControlPlane
    compliance: ComplianceLayer
    graph: GraphRelationshipEngine
    nlp: NLPIntelligenceLayer
    discovery: SearchDiscoveryLayer
    retrieval: RetrievalLayer

    @classmethod
    def from_settings(cls, settings: Settings) -> "AppServices":
        policy = PolicyEngine()
        return cls(
            policy=policy,
            crawl=CrawlControlPlane(),
            compliance=ComplianceLayer(
                settings.default_unknown_domain_delay_seconds,
                settings.domain_token_bucket_capacity,
                settings.domain_token_refill_per_second,
                settings.robots_cache_ttl_hours * 3600,
            ),
            graph=GraphRelationshipEngine(),
            nlp=NLPIntelligenceLayer(),
            discovery=SearchDiscoveryLayer(settings.enable_search_discovery),
            retrieval=RetrievalLayer(policy),
        )


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    logger.info("Starting %s in %s environment", settings.app_name, settings.environment)
    hydrate_runtime_llm(settings)
    app = FastAPI(
        title="ASAGUS Scraper 3.0 API",
        version=__version__,
        description="Intelligent 10-layer scraping, enrichment and retrieval platform.",
    )
    app.state.services = AppServices.from_settings(settings)
    allow_origins = settings.cors_origin_list or [settings.frontend_origin]
    if settings.environment == "local":
        allow_origins = [
            *allow_origins,
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:8000",
            "http://127.0.0.1:8000",
        ]
    allow_origins = list(dict.fromkeys(allow_origins))
    # In local environment, allow all origins for development convenience
    if settings.environment == "local":
        allow_origins = ["*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_credentials=settings.cors_allow_credentials if allow_origins != ["*"] else False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    _register_routers(app)
    return app


def _register_routers(app: FastAPI) -> None:
    """Register modular API routers and the root endpoint."""
    from asagus.routers.jobs import router as jobs_router
    from asagus.routers.records import router as records_router
    from asagus.routers.tools import router as tools_router
    from asagus.routers.settings import router as settings_router
    from asagus.routers.intelligence import router as intelligence_router
    from asagus.routers.agent_reach import router as agent_reach_router

    @app.get("/")
    async def root() -> dict[str, Any]:
        return {
            "app": "ASAGUS Scraper",
            "version": __version__,
            "status": "ready",
            "blueprint": "ASAGUS scrapper _3_0_v2.md",
        }
    
    # ✅ FIX #1: Persistence stats endpoint
    @app.get("/api/runtime/persistence-stats")
    async def get_persistence_stats() -> dict[str, Any]:
        """Get statistics about data persistence state."""
        return await runtime.get_persistence_stats()
    
    @app.post("/api/runtime/force-persist")
    async def force_persist_all() -> dict[str, Any]:
        """Force immediate persistence of all in-memory data."""
        return await runtime.force_persist_all()

    app.include_router(jobs_router)
    app.include_router(records_router)
    app.include_router(tools_router)
    app.include_router(settings_router)
    app.include_router(intelligence_router)
    app.include_router(agent_reach_router)


async def run_job(job_id: str, services: AppServices | None = None) -> None:
    job = runtime.jobs.get(job_id)
    if not job:
        return

    fetcher = None
    try:
        settings = get_settings()
        services = services or AppServices.from_settings(settings)
        policy = services.policy
        crawl = services.crawl
        compliance = services.compliance
        proxy_manager = ProxyPoolManager(proxy_urls_from_settings(settings))
        profile_name = "high" if job.request.mode == "max" else job.request.resource_profile
        resource_profile = resource_profile_for(
            profile_name,
            requested_workers=job.request.worker_count,
            settings_io=settings.crawl_concurrency_limit,
            settings_cpu=settings.cpu_worker_processes,
            settings_queue=settings.pipeline_queue_maxsize,
            settings_browser=settings.browser_pool_size,
        )
        discovery = services.discovery
        # ✅ FIX #4: Use relaxed thresholds for max/high-stealth modes
        use_relaxed_thresholds = job.request.mode in {"max"} or job.request.antibot_preset == "high-stealth"
        extractor = ExtractionLayer(get_llm_client(), use_relaxed_thresholds=use_relaxed_thresholds)
        enrichment = EnrichmentLayer(settings.google_geocoding_api_key)
        storage = StorageLayer(runtime, settings)
        indexer = IndexingLayer(settings)
        graph = services.graph
        planned_pages = planned_page_count(job.request, settings)
        processed_targets = 0
        skipped_targets = 0
        duplicate_skips = 0
        records_found = 0
        llm_calls = 0
        browser_renders = 0
        max_mode_tool_runs: list[dict[str, Any]] = []

        effective_network_fetch, effective_search_discovery = effective_runtime_flags(job.request, settings)
        resolved_website_filter = effective_website_filter(job.request)
        antibot_plan = antibot_preset_plan(job.request, settings)
        social_auth = SocialAuthLayer(settings, job.request)

        # Build antibot config from preset plan
        # Map browser engine to stealth approach
        browser_engine = antibot_plan.get("browser_engine", "playwright")
        if browser_engine == "camoufox":
            stealth_approach = StealthApproach.camoufox
        elif browser_engine == "patchright":
            stealth_approach = StealthApproach.patchright
        elif antibot_plan.get("behavioral_simulation", False):
            stealth_approach = StealthApproach.binary_patch
        else:
            stealth_approach = StealthApproach.javascript_shim
        
        antibot_config = AntiBotConfig(
            framework_priority=["antibot", "undetected", "scrapfly", "scrapeup"],
            stealth_approach=stealth_approach,
            tls_fingerprint=BrowserTLSFingerprint.chrome_124_windows,
            device_profile_name="desktop",
            enable_behavioral_simulation=antibot_plan.get("behavioral_simulation", True),
            enable_native_layer=antibot_plan.get("native_layer_requested", False),
            native_backend="cpp_pybind11",
            browser_automation_engine=browser_engine,
            browser_headless=settings.browser_headless,
            camoufox_binary_path=settings.camoufox_binary_path,
            proxy_url=None,
            enable_consistency_checks=True,
        )
        orchestrator = AntiBotOrchestrator(antibot_config)

        # Per-domain session store enables challenge-clearance cookie reuse so
        # a passed Cloudflare/DataDome interstitial is not re-triggered.
        session_store = None
        if settings.enable_session_reuse:
            sessions_dir = settings.session_store_dir or str(runtime.data_dir / "browser_sessions")
            session_store = SessionStore(sessions_dir, ttl_seconds=settings.session_ttl_seconds)

        fetcher = FetchLayer(
            enable_network_fetch=effective_network_fetch,
            proxy_manager=proxy_manager,
            browser_pool=ChromiumBrowserPool(
                pool_size=max(resource_profile.browser_contexts, 1),
                timeout_ms=job.request.max_seconds_per_page * 1000,
                engine=antibot_plan["browser_engine"],
                headless=settings.browser_headless,
                camoufox_binary_path=settings.camoufox_binary_path,
            ),
            social_auth_layer=social_auth,
            antibot_orchestrator=orchestrator,
            session_store=session_store,
            enable_escalation=settings.enable_escalation_ladder,
            max_escalation_step=EscalationStep[settings.escalation_max_step],
        )
        discovery = SearchDiscoveryLayer(effective_search_discovery)
        dom_tools = DOMTools()
        pages_by_domain: dict[str, int] = {}

        def prepare_candidate(candidate: URLCandidate) -> URLCandidate:
            candidate.metadata["allowed_domains"] = job.request.allowed_domains
            candidate.metadata["blocked_domains"] = job.request.blocked_domains
            candidate.metadata["proxy_strategy"] = job.request.proxy_strategy
            return social_auth.annotate_candidate(candidate)

        if job.status == JobStatus.cancelled:
            await emit(job_id, LayerName.ai_app, "job_cancelled", "Job cancelled before work started")
            return

        await runtime.update_job(
            job_id,
            status=JobStatus.running,
            started_at=utc_now(),
            total_targets=planned_pages,
            progress_message="Starting discovery",
        )
        await emit(job_id, LayerName.policy, "policy_ready", "Rule + Bayesian + feedback policy engine active")
        await emit(
            job_id,
            LayerName.ai_app,
            "runtime_mode",
            "Backend runtime gates resolved for this job",
            {
                "network_fetch": effective_network_fetch,
                "search_discovery": effective_search_discovery,
                "global_network_fetch": settings.enable_network_fetch,
                "global_search_discovery": settings.enable_search_discovery,
                "job_requested_network_fetch": job.request.enable_network_fetch,
                "job_requested_search_discovery": job.request.enable_search_discovery,
                "requested_website_filter": job.request.website_filter,
                "effective_website_filter": resolved_website_filter,
                "override_semantics": "explicit per-job True/False overrides backend defaults for educational research jobs",
            },
        )
        await emit(
            job_id,
            LayerName.fetch,
            "antibot_preset_resolved",
            "Anti-bot research preset mapped to the active fetch/browser path",
            {**antibot_plan, "browser_pool": fetcher.browser_pool.state()},
        )
        await emit(
            job_id,
            LayerName.social_auth,
            "social_auth_plan",
            "Social auth layer resolved for this job",
            social_auth.state(),
        )
        await emit(
            job_id,
            LayerName.crawl_control,
            "mode_plan",
            f"{job.request.mode} mode initialized",
            mode_plan(job.request, resource_profile, antibot_plan),
        )
        # ── Parallel Download-tool workers ──────────────────────────────────
        # Auto-launch the Download scraper tools as parallel workers for any
        # active scraping mode. MAX mode launches the full tool set; deeper
        # modes (deep, deep_agent, comprehensive, research, adaptive, parallel)
        # launch the scraper-worker subset. Each tool receives the real mode so
        # depth-aware tools (e.g. Maps scraper -> enhanced/deep/ultra/maximum)
        # pick the matching engine. API-only and outreach/messaging tools are
        # excluded by tools_runner.scraper_worker_tool_ids().
        _TOOL_WORKER_MODES = {
            "deep", "deep_agent", "comprehensive", "research", "adaptive", "parallel", "max",
        }
        if job.request.run_download_tools and job.request.mode in _TOOL_WORKER_MODES:
            from asagus.services.tools_runner import (
                launch_max_mode_tools,
                max_mode_tool_ids,
                scraper_worker_tool_ids,
            )
            from asagus.services.agent_reach_enrichment import get_enrichment_service

            if job.request.mode == "max":
                selected_tool_ids = max_mode_tool_ids()
                tools_scope = "max_all_tools"
            else:
                selected_tool_ids = scraper_worker_tool_ids()
                tools_scope = "scraper_workers"

            # Ensure Agent-Reach is available when it is part of the selection
            # (used as an enrichment/discovery co-engine, not a message sender).
            if "agent-reach" in selected_tool_ids:
                agent_reach = get_enrichment_service()
                if not agent_reach.is_available():
                    await emit(
                        job_id,
                        LayerName.ai_app,
                        "agent_reach_installing",
                        "Agent-Reach not found, attempting automatic installation",
                        {},
                    )
                    install_result = await agent_reach.ensure_installed()
                    await emit(
                        job_id,
                        LayerName.ai_app,
                        "agent_reach_install_result",
                        install_result["message"],
                        install_result,
                    )
                else:
                    await emit(
                        job_id,
                        LayerName.ai_app,
                        "agent_reach_ready",
                        "Agent-Reach co-engine is ready for enrichment",
                        {
                            "available_channels": agent_reach.enabled_channels,
                            "channel_count": len(agent_reach.enabled_channels),
                        },
                    )

            if selected_tool_ids:
                max_mode_tool_runs = await launch_max_mode_tools(
                    job_id=job_id,
                    query=job.request.query,
                    location=job.request.location,
                    limit=job.request.limit,
                    website_filter=resolved_website_filter,
                    network_enabled=effective_network_fetch,
                    tool_ids=selected_tool_ids,
                    mode=job.request.mode,
                )
                await emit(
                    job_id,
                    LayerName.ai_app,
                    "tool_workers_started",
                    f"Launched {len(max_mode_tool_runs)} Download tool worker(s) in parallel ({tools_scope})",
                    {
                        "count": len(max_mode_tool_runs),
                        "scope": tools_scope,
                        "mode": job.request.mode,
                        "tools": max_mode_tool_runs,
                    },
                )

        # Seed the initial frontier. Cap each discovery call at 200 results
        # (DDGS / HTML fallback practical limit) to avoid API overload, but
        # in offline mode the layer returns exactly max_results so we get a
        # full queue. Multiple refill passes top-up if the queue runs dry.
        seed_batch_size = min(max(planned_pages, 2), 200)  # per-call cap (real DDGS) or full (offline)
        discovery_results = await discovery.discover(
            SearchDiscoveryRequest(
                query=job.request.query,
                location=job.request.location,
                max_results=seed_batch_size,
                discovery_mode=job.request.discovery_mode,
                lead_target=job.request.lead_target,
                website_filter=resolved_website_filter,
                decision_maker_titles=job.request.decision_maker_titles,
            )
        )
        candidates = [result.candidate for result in discovery_results]
        if not candidates and not effective_search_discovery:
            candidates.extend(crawl.seed_from_query(job.request.query, job.request.location, job.request.limit))
        candidates = [prepare_candidate(candidate) for candidate in candidates]
        candidates = crawl.schedule(candidates)
        queue = candidates[:planned_pages]
        queued_urls = {runtime.url_key(candidate.url) for candidate in queue}
        await emit(
            job_id,
            LayerName.crawl_control,
            "frontier_seeded",
            "MDP frontier seeded and tiered",
            {
                "count": len(queue),
                "planned_pages": planned_pages,
                "target_records": job.request.limit,
                "mdp": [candidate.metadata.get("mdp_decision") for candidate in queue],
            },
        )

        _refill_attempts = 0
        _max_refill_attempts = 3  # guard against infinite loops when seeds are exhausted

        if job.request.mode == "max":
            page_parallelism = max(4, min(job.request.worker_count or resource_profile.io_concurrency, 16))
        elif job.request.mode == "parallel":
            page_parallelism = max(2, min(job.request.worker_count or resource_profile.io_concurrency, 8))
        elif job.request.mode in {"comprehensive", "research"} or job.request.resource_profile == "high":
            page_parallelism = max(2, min(max(resource_profile.browser_contexts, 1), 4))
        else:
            page_parallelism = 1
        candidate_timeout_seconds = max(job.request.max_seconds_per_page + 25, 30)

        await emit(
            job_id,
            LayerName.crawl_control,
            "worker_pool_ready",
            "Bounded page worker pool configured for this job",
            {
                "page_parallelism": page_parallelism,
                "candidate_timeout_seconds": candidate_timeout_seconds,
                "mode": job.request.mode,
                "resource_profile": job.request.resource_profile,
            },
        )

        async def _log_to_secondary_db(
            url: str, status: str, method: str = "", error_reason: str = "",
        ) -> None:
            """Write every candidate processing event to secondary DB for full audit trail."""
            try:
                domain = urlparse(url).netloc.lower()
                await runtime.add_secondary_record({
                    "job_id": job_id,
                    "url": url,
                    "domain": domain,
                    "status": status,
                    "method": method,
                    "error_reason": error_reason,
                    "query": job.request.query,
                    "location": job.request.location,
                    "mode": job.request.mode,
                    "timestamp": utc_now().isoformat(),
                })
            except Exception:
                return

        async def process_candidate(candidate: URLCandidate) -> dict[str, Any]:
            result: dict[str, Any] = {
                "processed": 1,
                "skipped": 0,
                "duplicates": 0,
                "records": 0,
                "llm_calls": 0,
                "browser_renders": 0,
                "followups": [],
                "cancelled": False,
            }
            try:
                async with asyncio.timeout(candidate_timeout_seconds):
                    current = runtime.jobs.get(job_id)
                    if current and current.status == JobStatus.cancelled:
                        result["cancelled"] = True
                        return result

                    await runtime.update_job(job_id, current_url=candidate.url, progress_message="Checking compliance")

                    if should_skip_url(candidate.url):
                        result["skipped"] = 1
                        await emit(
                            job_id,
                            LayerName.crawl_control,
                            "url_filter_skip",
                            "URL was skipped based on listing page patterns",
                            {"url": candidate.url},
                        )
                        await _log_to_secondary_db(candidate.url, "skipped", error_reason="url_filter")
                        return result

                    if job.request.skip_existing and await runtime.has_seen_url(candidate.url):
                        result["skipped"] = 1
                        await emit(
                            job_id,
                            LayerName.crawl_control,
                            "previously_seen_skip",
                            "URL was scraped in an earlier run and was skipped",
                            {"url": candidate.url},
                        )
                        await _log_to_secondary_db(candidate.url, "skipped", error_reason="previously_seen")
                        return result

                    comp = await compliance.check_async(
                        candidate,
                        job.request.allowed_domains,
                        job.request.blocked_domains,
                        respect_robots_txt=job.request.respect_robots_txt,
                        fetch_robots=effective_network_fetch,
                    )
                    if not comp.allowed and comp.reason == "domain_rate_limited" and comp.delay_seconds <= 15:
                        if not await sleep_or_cancel(job_id, comp.delay_seconds):
                            result["cancelled"] = True
                            return result
                        comp = await compliance.check_async(
                            candidate,
                            job.request.allowed_domains,
                            job.request.blocked_domains,
                            respect_robots_txt=job.request.respect_robots_txt,
                            fetch_robots=effective_network_fetch,
                        )
                    await emit(job_id, LayerName.compliance, "compliance_checked", comp.reason, comp.model_dump())
                    if not comp.allowed:
                        result["skipped"] = 1
                        await _log_to_secondary_db(candidate.url, "skipped", error_reason=f"compliance:{comp.reason}")
                        return result

                    decision = policy.decide_for_url(candidate, llm_enabled=job.request.llm_enabled)
                    await emit(job_id, LayerName.policy, "decision", "URL routed by policy engine", decision.model_dump())
                    if decision.decision == "skip":
                        result["skipped"] = 1
                        await runtime.mark_url_seen(candidate.url)
                        await _log_to_secondary_db(candidate.url, "skipped", error_reason="policy_skip")
                        return result
                    if decision.decision == "defer":
                        result["skipped"] = 1
                        await emit(
                            job_id,
                            LayerName.policy,
                            "deferred",
                            "URL deferred by policy and left for a later run",
                            {"url": candidate.url, "next_review_seconds": decision.next_review_seconds or 3600},
                        )
                        await _log_to_secondary_db(candidate.url, "deferred", error_reason="policy_defer")
                        return result

                    auth_context = social_auth.resolve(candidate.url)
                    if auth_context.enabled:
                        await emit(
                            job_id,
                            LayerName.social_auth,
                            "social_auth_selected" if auth_context.session_available else "social_auth_session_missing",
                            "Social platform URL routed through the isolated auth layer",
                            auth_context.public_payload(),
                        )

                    if effective_network_fetch and comp.delay_seconds > 0:
                        await runtime.update_job(job_id, progress_message=f"Waiting {comp.delay_seconds}s for crawl pacing")
                        await emit(
                            job_id,
                            LayerName.compliance,
                            "crawl_delay",
                            "Waiting before fetch to honor crawl pacing",
                            {"url": candidate.url, "delay_seconds": comp.delay_seconds, "source": comp.crawl_delay_source},
                        )
                        if not await sleep_or_cancel(job_id, comp.delay_seconds):
                            result["cancelled"] = True
                            return result

                    await runtime.update_job(job_id, current_url=candidate.url, progress_message="Fetching page")
                    fetch = await fetcher.fetch(candidate, decision)
                    await runtime.mark_url_seen(candidate.url)
                    await emit(job_id, LayerName.fetch, "fetch_complete", "Fetch layer completed", fetch.model_dump(exclude={"html"}))

                    extracted = None
                    if fetch.error == "offline_preview_only":
                        fallback_record = candidate_partial_record(candidate, job.request, "Offline preview social/place candidate")
                        if fallback_record:
                            extracted = fallback_record
                            await emit(
                                job_id,
                                LayerName.extraction,
                                "candidate_partial_record",
                                "Stored a social/place preview as a partial no-owned-website lead",
                                extracted.model_dump(),
                            )
                        else:
                            result["skipped"] = 1
                            await emit(
                                job_id,
                                LayerName.fetch,
                                "offline_preview_skipped",
                                "Offline preview output is not stored as a business lead",
                                {"url": candidate.url},
                            )
                            return result

                    archive_info: dict[str, str] = {}
                    if job.request.archive_raw_html and fetch.html:
                        archive_info = await storage.archive_raw_html(job_id, fetch)
                        if archive_info:
                            await emit(
                                job_id,
                                LayerName.storage,
                                "raw_html_archived",
                                "Raw HTML archived for audit and replay",
                                archive_info,
                            )

                    page_evidence: dict[str, Any] = {}
                    if fetch.html:
                        challenge = dom_tools.detect_challenge(fetch.html, fetch.status_code)
                        if job.request.capture_dom_fingerprint:
                            page_evidence["dom_fingerprint"] = dom_tools.fingerprint(fetch.html, fetch.final_url or fetch.url)
                        if job.request.capture_device_stamp:
                            page_evidence["device_stamp"] = dom_tools.device_stamp(
                                fetch_mode=fetch.fetch_mode.value,
                                render_time_ms=fetch.render_time_ms,
                                status_code=fetch.status_code,
                            )
                        page_evidence["challenge"] = challenge
                        if page_evidence:
                            await emit(
                                job_id,
                                LayerName.extraction,
                                "page_evidence",
                                "DOM fingerprint, device stamp and challenge signals captured",
                                page_evidence,
                            )
                        if challenge["challenge_detected"] and job.request.manual_review_on_challenge:
                            result["skipped"] = 1
                            await emit(
                                job_id,
                                LayerName.compliance,
                                "manual_review_challenge",
                                "Challenge or access-control signal detected; no bypass was attempted",
                                challenge,
                            )
                            return result

                    if fetch.html:
                        remaining_slots = max(0, planned_pages - len(queue) - processed_targets + 20)
                        if remaining_slots:
                            followups = discovery.followup_candidates(
                                fetch.html,
                                candidate.url,
                                job.request.query,
                                job.request.location,
                                candidate.depth,
                                include_contact_pages=job.request.include_contact_pages,
                                include_social_profiles=job.request.include_social_profiles,
                                limit=min(20, remaining_slots),
                            )
                            for followup in followups:
                                prepare_candidate(followup)
                            result["followups"] = crawl.schedule(followups)

                    if extracted is None and fetch.error and not fetch.html:
                        fallback_record = candidate_partial_record(candidate, job.request, f"Fetch failed without HTML: {fetch.error}")
                        if not fallback_record:
                            result["skipped"] = 1
                            await emit(job_id, LayerName.fetch, "fetch_empty", "Fetch failed and no HTML was available", {"url": candidate.url, "error": fetch.error})
                            return result
                        extracted = fallback_record
                        await emit(
                            job_id,
                            LayerName.extraction,
                            "candidate_partial_record",
                            "Stored a social/place candidate as a partial no-owned-website lead after fetch failure",
                            extracted.model_dump(),
                        )
                    elif extracted is None:
                        await runtime.update_job(job_id, current_url=candidate.url, progress_message="Extracting business data")
                        extracted = await extractor.extract(fetch, decision, job.request.llm_enabled)

                        # --- Step 5: Non-destructive noise reduction + scoring ---
                        # Clean fields and compute a quality score WITHOUT
                        # dropping records (noise reduction / data-validation
                        # SKILLs). Phone normalization keeps the raw value as a
                        # fallback so we never lose a contact just because it
                        # failed strict E.164 parsing.
                        logger.debug(
                            "Raw extracted record for %s: %s",
                            candidate.url,
                            extracted.model_dump() if extracted else None,
                        )
                        normalized_phone = normalize_phone(extracted.phone, location=job.request.location)
                        normalized_whatsapp = normalize_phone(extracted.whatsapp, location=job.request.location)
                        extracted.phone = normalized_phone or (extracted.phone or "").strip()
                        extracted.whatsapp = normalized_whatsapp or (extracted.whatsapp or "").strip()

                        has_contact = bool(extracted.phone or extracted.whatsapp or extracted.email)
                        cleaning = clean_record_fields(
                            {
                                "name": extracted.name,
                                "address": extracted.address,
                                "city": extracted.city,
                                "category": extracted.category,
                            },
                            has_contact=has_contact,
                        )
                        extracted.name = cleaning.fields["name"]
                        extracted.address = cleaning.fields["address"]
                        extracted.city = cleaning.fields["city"]
                        extracted.category = cleaning.fields["category"]
                        # Blend cleaning quality into the extraction confidence
                        # so low-quality records are flagged, not discarded.
                        extracted.confidence = round(
                            min(extracted.confidence or 0.0, cleaning.confidence)
                            if extracted.confidence
                            else cleaning.confidence,
                            3,
                        )
                        extracted.raw_fields = {
                            **extracted.raw_fields,
                            "cleaning_confidence": cleaning.confidence,
                            "cleaning_issues": cleaning.issues,
                            "phone_normalized": bool(normalized_phone),
                            "whatsapp_normalized": bool(normalized_whatsapp),
                        }
                        logger.debug(
                            "Cleaned record for %s name=%r confidence=%.3f issues=%s",
                            candidate.url,
                            extracted.name,
                            cleaning.confidence,
                            cleaning.issues,
                        )

                        # --- Step 6: Keep record even without a name; flag it ---
                        # Records with no business name are no longer dropped.
                        # They are marked for review and given a synthetic
                        # placeholder so they still reach the CSV.
                        if not extracted.name:
                            extracted.manual_review_required = True
                            extracted.raw_fields["name_missing"] = True
                            await emit(
                                job_id,
                                LayerName.extraction,
                                "name_missing_flagged",
                                "Business name empty after cleaning; record kept and flagged for review",
                                {"url": candidate.url, "confidence": extracted.confidence},
                            )

                        if archive_info:
                            extracted = extracted.model_copy(
                                update={"raw_fields": {**extracted.raw_fields, "raw_html_archive": archive_info}}
                            )
                        if page_evidence:
                            extracted = extracted.model_copy(
                                update={"raw_fields": {**extracted.raw_fields, "page_evidence": page_evidence}}
                            )
                        extracted = merge_candidate_partial_record(
                            extracted,
                            candidate,
                            job.request,
                            "Social/place candidate kept for no-owned-website discovery",
                        )
                        await emit(
                            job_id,
                            LayerName.extraction,
                            "extract_complete",
                            "Extraction cascade completed",
                            extracted.model_dump(),
                        )
                    if not useful_record(extracted) and not (
                        job.request.store_partial_records and partial_record(extracted)
                    ):
                        result["skipped"] = 1
                        await emit(
                            job_id,
                            LayerName.extraction,
                            "no_business_fields",
                            "No email, phone, social profile, or useful business identity was found",
                            extracted.model_dump(),
                        )
                        return result
                    if not useful_record(extracted):
                        extracted = extracted.model_copy(
                            update={
                                "raw_fields": {
                                    **extracted.raw_fields,
                                    "partial_record": True,
                                    "partial_reason": "Stored because store_partial_records is enabled",
                                }
                            }
                        )
                    if job.request.require_email and not extracted.email:
                        result["skipped"] = 1
                        await emit(
                            job_id,
                            LayerName.extraction,
                            "email_required_skip",
                            "Record is missing email and was skipped because require_email is enabled",
                            extracted.model_dump(),
                        )
                        return result
                    if not website_filter_allows(extracted, resolved_website_filter):
                        result["skipped"] = 1
                        await emit(
                            job_id,
                            LayerName.extraction,
                            "website_filter_skip",
                            "Record did not match the requested website filter",
                            {
                                "url": candidate.url,
                                "website_filter": resolved_website_filter,
                                "requested_website_filter": job.request.website_filter,
                                "website_url": extracted.website_url,
                            },
                        )
                        return result

                    await runtime.update_job(job_id, current_url=candidate.url, progress_message="Enriching and deduping")
                    enriched = await enrichment.enrich(extracted, default_city=job.request.location)
                    
                    # ✅ PHASE 4: Agent-Reach enrichment in MAX mode
                    if job.request.mode == "max":
                        from asagus.services.agent_reach_enrichment import get_enrichment_service
                        agent_reach = get_enrichment_service()
                        
                        if agent_reach.is_available():
                            enriched_dict = enriched.model_dump()
                            enriched_dict = await agent_reach.enrich_business_record(
                                enriched_dict,
                                enable_web_scraping=effective_network_fetch,
                                enable_social_search=False  # Enable when social auth is ready
                            )
                            # Update the enriched model with Agent-Reach data
                            if enriched_dict.get("agent_reach_enriched"):
                                # Merge Agent-Reach findings back into the record
                                enriched = enriched.model_copy(update={
                                    "email": enriched_dict.get("email") or enriched.email,
                                    "phone": enriched_dict.get("phone") or enriched.phone,
                                    "raw_fields": {
                                        **enriched.raw_fields,
                                        "agent_reach_data": enriched_dict.get("agent_reach_data", {}),
                                        "agent_reach_channels": enriched_dict.get("agent_reach_channels_used", []),
                                    }
                                })
                                await emit(
                                    job_id,
                                    LayerName.enrichment,
                                    "agent_reach_enriched",
                                    "Record enriched by Agent-Reach co-engine",
                                    {
                                        "channels_used": enriched_dict.get("agent_reach_channels_used", []),
                                        "email_found": bool(enriched_dict.get("agent_reach_data", {}).get("found_emails")),
                                        "phone_found": bool(enriched_dict.get("agent_reach_data", {}).get("found_phones")),
                                    }
                                )
                    
                    existing_records = await runtime.list_records()
                    duplicate_scores = [enrichment.dedupe_score(enriched, existing) for existing in existing_records]
                    if duplicate_scores:
                        best_score, reasons = sorted(duplicate_scores, key=lambda item: item[0], reverse=True)[0]
                        enriched = enriched.model_copy(update={"duplicate_score": best_score, "dedupe_reasons": reasons})
                    await emit(
                        job_id,
                        LayerName.enrichment,
                        "enrich_complete",
                        "Record enriched and validated",
                        enriched.model_dump(),
                    )

                    stored_record, is_new, duplicate_reasons = await storage.store_record(enriched)
                    if is_new:
                        result["records"] = 1
                        await emit(job_id, LayerName.storage, "stored", "Record stored", {"record_id": stored_record.id})
                    else:
                        result["duplicates"] = 1
                        await emit(
                            job_id,
                            LayerName.storage,
                            "duplicate_merged",
                            "Duplicate record merged instead of adding a repeated row",
                            {"record_id": stored_record.id, "reasons": duplicate_reasons},
                        )

                    graph_candidates = graph.candidates_for(stored_record, existing_records)
                    await runtime.add_graph_candidates(graph_candidates)
                    if graph_candidates:
                        await emit(
                            job_id,
                            LayerName.storage,
                            "graph_candidates",
                            "Neo4j relationship candidates generated",
                            {"count": len(graph_candidates), "relationships": [item.model_dump(mode="json") for item in graph_candidates]},
                        )

                    index_result = await indexer.index(stored_record)
                    await emit(job_id, LayerName.indexing, "index_queued", "Indexes updated or queued", index_result)

                    if extracted.method.value == "llm":
                        result["llm_calls"] = 1
                    if decision.fetch_mode.value == "dynamic":
                        result["browser_renders"] = 1

                    feedback = PolicyFeedback(
                        domain=urlparse(candidate.url).netloc.lower(),
                        extraction_confidence=extracted.confidence,
                        fields_extracted=len([field for field in extracted.model_dump().values() if isinstance(field, str) and field]),
                        render_time_ms=fetch.render_time_ms,
                        proxy_cost=0.08 if decision.fetch_mode.value == "dynamic" else 0.01,
                        was_blocked=fetch.status_code in {403, 429},
                        used_llm=extracted.method.value == "llm",
                        used_browser=decision.fetch_mode.value == "dynamic",
                    )
                    policy.record_feedback(feedback)
                    mdp_payload = candidate.metadata.get("mdp_decision") or {}
                    if isinstance(mdp_payload, dict) and mdp_payload.get("action"):
                        try:
                            mdp_action = MDPAction(str(mdp_payload["action"]))
                            outcome = crawl.scheduler.infer_outcome(
                                fields_extracted=feedback.fields_extracted,
                                confidence=feedback.extraction_confidence,
                                blocked=feedback.was_blocked,
                            )
                            reward = (
                                feedback.fields_extracted * feedback.extraction_confidence
                                - (feedback.render_time_ms / 1000) * feedback.proxy_cost
                                - (1.4 if feedback.was_blocked else 0)
                            )
                            crawl.scheduler.record_reward(
                                mdp_action,
                                reward=reward,
                                state_key=str(mdp_payload.get("state_key") or ""),
                                outcome=outcome,
                            )
                        except ValueError:
                            pass
                    # Log successful processing to secondary DB
                    status = "stored" if result["records"] else ("duplicate" if result["duplicates"] else "processed")
                    await _log_to_secondary_db(candidate.url, status, method=extracted.method.value if extracted else "")
                    return result
            except TimeoutError:
                result["skipped"] = 1
                await runtime.mark_url_seen(candidate.url)
                await emit(
                    job_id,
                    LayerName.ai_app,
                    "candidate_timeout",
                    "Candidate processing exceeded the configured page watchdog and was skipped",
                    {"url": candidate.url, "timeout_seconds": candidate_timeout_seconds},
                )
                await _log_to_secondary_db(candidate.url, "timeout", error_reason="candidate_timeout")
                return result
            except Exception as exc:
                result["skipped"] = 1
                await emit(
                    job_id,
                    LayerName.ai_app,
                    "candidate_failed",
                    "Candidate failed without stopping the whole job",
                    {"url": candidate.url, "error": str(exc)},
                )
                await _log_to_secondary_db(candidate.url, "failed", error_reason=str(exc)[:200])
                return result

        while (queue or _refill_attempts < _max_refill_attempts) and processed_targets < planned_pages and records_found < job.request.limit:

            # If the queue is empty but we haven't hit the limit yet, try to
            # refill it before giving up.  This is the critical fix for the
            # "scraper stops early" bug: it ensures we keep going even when the
            # initial seed set is exhausted.
            if not queue:
                if _refill_attempts >= _max_refill_attempts:
                    break
                _refill_attempts += 1
                extra_seeds = []
                if job.request.discovery_mode != "social_only":
                    extra_seeds = crawl.seed_from_query(
                        job.request.query, job.request.location, job.request.limit
                    )
                extra_seeds += await _discovery_refill(discovery, job.request, planned_pages, queued_urls, _refill_attempts)
                added_count = 0
                extra_seeds = [prepare_candidate(seed) for seed in extra_seeds]
                for seed in crawl.schedule(extra_seeds):
                    key = runtime.url_key(seed.url)
                    if key not in queued_urls:
                        queued_urls.add(key)
                        queue.append(seed)
                        added_count += 1
                if queue:
                    await emit(
                        job_id,
                        LayerName.crawl_control,
                        "frontier_refilled",
                        f"Queue refill #{_refill_attempts}: added {added_count} seeds",
                        {"added": added_count, "records_found": records_found, "limit": job.request.limit},
                    )
                else:
                    # Truly exhausted — nothing more to crawl.
                    break

            batch_limit = min(page_parallelism, planned_pages - processed_targets, job.request.limit - records_found)
            batch: list[URLCandidate] = []
            while queue and len(batch) < batch_limit and processed_targets + len(batch) < planned_pages:
                candidate = queue.pop(0)
                candidate_domain = urlparse(candidate.url).netloc.lower()
                if job.request.max_pages_per_domain:
                    pages_by_domain[candidate_domain] = pages_by_domain.get(candidate_domain, 0) + 1
                    if pages_by_domain[candidate_domain] > job.request.max_pages_per_domain:
                        processed_targets += 1
                        skipped_targets += 1
                        await runtime.update_job(
                            job_id,
                            processed_targets=processed_targets,
                            skipped_targets=skipped_targets,
                            progress_message="Skipped by per-domain page cap",
                        )
                        await emit(
                            job_id,
                            LayerName.crawl_control,
                            "domain_page_cap_skip",
                            "URL skipped because the job's per-domain cap was reached",
                            {"domain": candidate_domain, "cap": job.request.max_pages_per_domain, "url": candidate.url},
                        )
                        continue
                batch.append(candidate)

            if not batch:
                continue

            current = runtime.jobs.get(job_id)
            if current and current.status == JobStatus.cancelled:
                await runtime.update_job(
                    job_id,
                    finished_at=utc_now(),
                    processed_targets=processed_targets,
                    skipped_targets=skipped_targets,
                    duplicate_skips=duplicate_skips,
                    records_found=records_found,
                    progress_message="Cancelled; stored records were kept",
                    current_url="",
                )
                await emit(
                    job_id,
                    LayerName.ai_app,
                    "job_cancelled",
                    "Worker stopped before the next page batch; stored records were kept",
                    {"records_found": records_found, "processed_targets": processed_targets},
                )
                return

            await runtime.update_job(
                job_id,
                processed_targets=processed_targets,
                skipped_targets=skipped_targets,
                duplicate_skips=duplicate_skips,
                records_found=records_found,
                llm_calls=llm_calls,
                browser_renders=browser_renders,
                current_url=batch[0].url,
                progress_message=f"Processing {len(batch)} page{'s' if len(batch) != 1 else ''}",
            )

            batch_results = await asyncio.gather(
                *(process_candidate(candidate) for candidate in batch),
                return_exceptions=True,
            )
            for candidate, item in zip(batch, batch_results):
                if isinstance(item, Exception):
                    processed_targets += 1
                    skipped_targets += 1
                    error_message = str(item)
                    await emit(
                        job_id,
                        LayerName.ai_app,
                        "candidate_worker_exception",
                        "Candidate worker failed and was skipped without stopping the job",
                        {"url": candidate.url, "error": error_message},
                    )
                    await _log_to_secondary_db(candidate.url, "failed", error_reason=error_message[:200])
                    continue
                if item.get("cancelled"):
                    await runtime.update_job(
                        job_id,
                        finished_at=utc_now(),
                        processed_targets=processed_targets,
                        skipped_targets=skipped_targets,
                        duplicate_skips=duplicate_skips,
                        records_found=records_found,
                        progress_message="Cancelled; stored records were kept",
                        current_url="",
                    )
                    return
                processed_targets += int(item.get("processed", 0))
                skipped_targets += int(item.get("skipped", 0))
                duplicate_skips += int(item.get("duplicates", 0))
                records_found += int(item.get("records", 0))
                llm_calls += int(item.get("llm_calls", 0))
                browser_renders += int(item.get("browser_renders", 0))
                new_followups = []
                for followup in item.get("followups", []):
                    key = runtime.url_key(followup.url)
                    if key in queued_urls:
                        continue
                    if job.request.skip_existing and await runtime.has_seen_url(followup.url):
                        continue
                    queued_urls.add(key)
                    new_followups.append(followup)
                if new_followups:
                    queue.extend(new_followups)
                    await emit(
                        job_id,
                        LayerName.crawl_control,
                        "followups_discovered",
                        "Contact and social follow-up links were added to the frontier",
                        {"count": len(new_followups), "urls": [item.url for item in list(new_followups)[:12]]},
                    )

            await runtime.update_job(
                job_id,
                processed_targets=processed_targets,
                skipped_targets=skipped_targets,
                duplicate_skips=duplicate_skips,
                records_found=records_found,
                llm_calls=llm_calls,
                browser_renders=browser_renders,
                progress_message=f"Stored {records_found}/{job.request.limit} requested records",
            )


        current = runtime.jobs.get(job_id)
        if current and current.status == JobStatus.cancelled:
            await runtime.update_job(
                job_id,
                finished_at=utc_now(),
                processed_targets=processed_targets,
                skipped_targets=skipped_targets,
                duplicate_skips=duplicate_skips,
                records_found=records_found,
                progress_message="Cancelled; stored records were kept",
                current_url="",
            )
            await emit(
                job_id,
                LayerName.ai_app,
                "job_cancelled",
                "Pipeline cancelled; stored records were kept",
                {"records_found": records_found, "processed_targets": processed_targets},
            )
            return

        if job.request.mode == "max":
            from asagus.services.csv_merger import merge_asagus_and_download_csv
            from asagus.services.tools_runner import wait_for_job_tools

            merge_wait_seconds = float(os.getenv("ASAGUS_MAX_MODE_TOOL_MERGE_WAIT_SECONDS", "240"))
            tool_wait = await wait_for_job_tools(job_id, timeout_seconds=merge_wait_seconds)
            await emit(
                job_id,
                LayerName.ai_app,
                "max_mode_tools_finished",
                "MAX mode co-engine tool runs reached a terminal state or the merge wait window ended",
                tool_wait,
            )
            primary_records = [
                record.model_dump(mode="json")
                for record in await runtime.list_records()
            ]
            merge_result = merge_asagus_and_download_csv(job_id, primary_records)
            await runtime.add_secondary_record({
                "job_id": job_id,
                "status": "combined_csv_ready",
                "method": "max_mode_merge",
                "query": job.request.query,
                "location": job.request.location,
                "mode": job.request.mode,
                "timestamp": utc_now().isoformat(),
                "output_csv": merge_result.get("output_csv", ""),
                "records_merged": merge_result.get("records_merged", 0),
                "tools_merged": ",".join(merge_result.get("tools_merged", [])),
            })
            await emit(
                job_id,
                LayerName.storage,
                "combined_csv_ready",
                "Primary ASAGUS records and Download tool outputs were merged into one job CSV",
                merge_result,
            )

        await runtime.update_job(
            job_id,
            status=JobStatus.completed,
            finished_at=utc_now(),
            processed_targets=processed_targets,
            skipped_targets=skipped_targets,
            duplicate_skips=duplicate_skips,
            records_found=records_found,
            progress_message="Completed",
            current_url="",
        )
        await emit(job_id, LayerName.ai_app, "job_completed", "Pipeline completed")
    except Exception as exc:
        await runtime.update_job(job_id, status=JobStatus.failed, finished_at=utc_now(), error=str(exc))
        await emit(job_id, LayerName.ai_app, "job_failed", str(exc), {"error": str(exc)})
    finally:
        if fetcher is not None:
            try:
                await fetcher.close()
            except Exception:
                pass


app = create_app()
