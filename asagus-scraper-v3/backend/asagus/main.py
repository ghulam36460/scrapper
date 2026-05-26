from __future__ import annotations

import asyncio
from datetime import timezone
from typing import Any
from urllib.parse import urlparse

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import SecretStr

from asagus import __version__
from asagus.config import Settings, get_settings
from asagus.layers.ai_app import AIApplicationLayer
from asagus.layers.analytics import PredictiveAnalyticsLayer
from asagus.layers.browser import ChromiumBrowserPool
from asagus.layers.compliance import ComplianceLayer
from asagus.layers.crawl_control import CrawlControlPlane
from asagus.layers.discovery import SearchDiscoveryLayer
from asagus.layers.dom_tools import DOMTools
from asagus.layers.enrichment import EnrichmentLayer
from asagus.layers.extraction import ExtractionLayer
from asagus.layers.fetch import FetchLayer
from asagus.layers.geoint import GeospatialIntelligenceLayer
from asagus.layers.graph import GraphRelationshipEngine
from asagus.layers.indexing import IndexingLayer
from asagus.layers.nlp_intelligence import NLPIntelligenceLayer
from asagus.layers.observability import ObservabilityLayer
from asagus.layers.osint import SafeOSINTLayer
from asagus.layers.policy import PolicyEngine
from asagus.layers.proxy import ProxyPoolManager
from asagus.layers.retrieval import RetrievalLayer
from asagus.layers.search_index import InvertedSearchIndex
from asagus.layers.storage import StorageLayer
from asagus.layers.throughput import AsyncCPUHybridExecutor
from asagus.layers.vision import ComputerVisionLayer
from asagus.llm.providers import LLMClient, provider_catalog
from asagus.models import (
    JobEvent,
    JobStatus,
    LLMProvider,
    LLMSettings,
    LayerName,
    CapabilityCard,
    MDPAction,
    PolicyFeedback,
    SearchDiscoveryRequest,
    ScrapeJob,
    ScrapeStartRequest,
    SearchRequest,
    ThroughputProfile,
    URLCandidate,
    utc_now,
)
from asagus.services.health import collect_health
from asagus.services.runtime import runtime


def create_app() -> FastAPI:
    settings = get_settings()
    hydrate_runtime_llm(settings)
    app = FastAPI(
        title="ASAGUS Scraper 3.0 API",
        version=__version__,
        description="Intelligent 10-layer scraping, enrichment and retrieval platform.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            settings.frontend_origin,
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:8000",
            "http://127.0.0.1:8000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_routes(app)
    return app

def get_llm_client() -> LLMClient | None:
    if runtime.llm_settings.provider == LLMProvider.disabled:
        return None
    return LLMClient(runtime.llm_settings)


def register_routes(app: FastAPI) -> None:
    @app.get("/")
    async def root() -> dict[str, Any]:
        return {
            "app": "ASAGUS Scraper",
            "version": __version__,
            "status": "ready",
            "blueprint": "ASAGUS scrapper _3_0_v2.md",
        }

    @app.get("/api/blueprint")
    async def blueprint() -> dict[str, Any]:
        return {
            "version": "3.0",
            "source_of_truth": "ASAGUS scrapper _3_0_v2.md",
            "layers": [
                {"id": 0, "key": "policy", "name": "Policy Engine", "status": "rules_bayesian_feedback"},
                {"id": 1, "key": "crawl_control", "name": "Crawl Control Plane", "status": "mdp_frontier_scheduler"},
                {"id": 2, "key": "compliance", "name": "Compliance Layer", "status": "robots_token_bucket_audit"},
                {"id": 3, "key": "fetch", "name": "Fetch Layer", "status": "static_dynamic_proxy_pool"},
                {"id": 4, "key": "extraction", "name": "Extraction Layer", "status": "self_healing_cascade"},
                {"id": 5, "key": "enrichment", "name": "Enrichment Layer", "status": "ner_validation_dedupe"},
                {"id": 6, "key": "storage", "name": "Storage Layer", "status": "local_and_postgres_contracts"},
                {"id": 7, "key": "indexing", "name": "Indexing Layer", "status": "opensearch_qdrant_contracts"},
                {"id": 8, "key": "retrieval", "name": "Retrieval Layer", "status": "bm25_dense_rrf"},
                {"id": 9, "key": "ai_app", "name": "AI Application Layer", "status": "any_llm_provider_registry"},
            ],
        }

    @app.get("/api/providers")
    async def providers() -> dict[str, Any]:
        return {"providers": [preset.model_dump(mode="json") for preset in provider_catalog()]}

    @app.get("/api/algorithm/state")
    async def algorithm_state(settings: Settings = Depends(get_settings)) -> dict[str, Any]:
        policy = PolicyEngine()
        crawl = CrawlControlPlane()
        compliance = ComplianceLayer(
            settings.default_unknown_domain_delay_seconds,
            settings.domain_token_bucket_capacity,
            settings.domain_token_refill_per_second,
            settings.robots_cache_ttl_hours * 3600,
        )
        proxy = ProxyPoolManager()
        graph = GraphRelationshipEngine()
        observability = ObservabilityLayer()
        nlp = NLPIntelligenceLayer()
        osint = SafeOSINTLayer()
        dom_tools = DOMTools()
        analytics = PredictiveAnalyticsLayer()
        geoint = GeospatialIntelligenceLayer()
        vision = ComputerVisionLayer()
        throughput = AsyncCPUHybridExecutor(
            ThroughputProfile(
                io_concurrency=settings.crawl_concurrency_limit,
                cpu_workers=settings.cpu_worker_processes,
                queue_maxsize=settings.pipeline_queue_maxsize,
                browser_contexts=settings.browser_pool_size,
            )
        )
        retrieval = RetrievalLayer(policy)
        records = await runtime.list_records()
        index_state = InvertedSearchIndex().build(records).state()
        return {
            "policy": {**policy.stats(), "domains": [state.model_dump(mode="json") for state in policy.domain_states()[:10]]},
            "mdp": crawl.algorithm_state(),
            "compliance": compliance.stats(),
            "proxy": proxy.state(),
            "discovery": SearchDiscoveryLayer(settings.enable_search_discovery).state(),
            "throughput": throughput.state(),
            "extraction": {
                "cascade": [
                    {"stage": "CSS/XPath", "accept_confidence": ExtractionLayer.CSS_ACCEPT},
                    {"stage": "DOM Fingerprint", "accept_confidence": ExtractionLayer.FINGERPRINT_ACCEPT},
                    {"stage": "Structural Heuristics", "accept_confidence": ExtractionLayer.STRUCTURAL_ACCEPT},
                    {"stage": "LLM Extraction", "accept_confidence": 0.50},
                    {"stage": "Manual Review", "accept_confidence": "<0.50"},
                ],
                "llm_cache_days": settings.llm_fallback_cache_days,
            },
            "graph": graph.state(),
            "search_algorithms": [item.model_dump(mode="json") for item in retrieval.algorithm_catalog()],
            "index_state": index_state,
            "nlp": nlp.state(),
            "osint": osint.state(),
            "dom_tools": dom_tools.state(),
            "analytics": analytics.state(),
            "geoint": geoint.state(),
            "vision": vision.state(),
            "capabilities": capability_catalog(),
            "observability_catalog": observability.catalog(),
        }

    @app.post("/api/discovery/search")
    async def discovery_search(payload: SearchDiscoveryRequest, settings: Settings = Depends(get_settings)) -> dict[str, Any]:
        discovery = SearchDiscoveryLayer(settings.enable_search_discovery)
        results = await discovery.discover(payload)
        return {"count": len(results), "results": results}

    @app.get("/api/health")
    async def health(settings: Settings = Depends(get_settings)) -> Any:
        return await collect_health(settings)

    @app.get("/api/llm/settings")
    async def get_llm_settings() -> dict[str, Any]:
        return runtime.llm_settings.masked()

    @app.post("/api/llm/settings")
    async def set_llm_settings(payload: LLMSettings) -> dict[str, Any]:
        runtime.llm_settings = normalize_llm_settings(payload)
        return runtime.llm_settings.masked()

    @app.get("/api/jobs")
    async def list_jobs() -> list[ScrapeJob]:
        return await runtime.list_jobs()

    @app.post("/api/jobs")
    async def start_job(payload: ScrapeStartRequest, tasks: BackgroundTasks, settings: Settings = Depends(get_settings)) -> ScrapeJob:
        job = ScrapeJob(
            request=payload,
            total_targets=planned_page_count(payload, settings),
            progress_message="Queued",
        )
        await runtime.add_job(job)
        await emit(job.id, LayerName.ai_app, "job_queued", "Job queued from dashboard", payload.model_dump())
        tasks.add_task(run_job, job.id)
        return job

    @app.get("/api/jobs/{job_id}")
    async def get_job(job_id: str) -> dict[str, Any]:
        job = runtime.jobs.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return {"job": job, "events": await runtime.list_events(job_id)}

    @app.post("/api/jobs/{job_id}/cancel")
    async def cancel_job(job_id: str) -> ScrapeJob:
        job = await runtime.cancel_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        if job.status == JobStatus.cancelled:
            await emit(job.id, LayerName.ai_app, "job_cancelled", "Job cancelled by operator")
        return job

    @app.post("/api/policy/decision")
    async def policy_decision(candidate: URLCandidate) -> Any:
        policy = PolicyEngine()
        return policy.decide_for_url(candidate, llm_enabled=runtime.llm_settings.provider != LLMProvider.disabled)

    @app.get("/api/policy/stats")
    async def policy_stats() -> dict[str, Any]:
        stats = PolicyEngine().stats()
        stats.update(runtime.policy_stats)
        return stats

    @app.get("/api/policy/domains")
    async def policy_domains() -> dict[str, Any]:
        return {"domains": [state.model_dump(mode="json") for state in PolicyEngine().domain_states()]}

    @app.get("/api/records")
    async def records() -> dict[str, Any]:
        rows = await runtime.list_records()
        return {"count": len(rows), "records": rows}

    @app.get("/api/graph/candidates")
    async def graph_candidates() -> dict[str, Any]:
        rows = await runtime.list_graph_candidates()
        return {"count": len(rows), "candidates": rows}

    @app.get("/api/observability")
    async def observability() -> dict[str, Any]:
        policy = PolicyEngine().stats()
        jobs = await runtime.list_jobs()
        metrics = ObservabilityLayer().from_runtime(jobs, policy)
        return {"metrics": metrics}

    @app.get("/api/intelligence")
    async def intelligence() -> dict[str, Any]:
        records = await runtime.list_records()
        nlp = NLPIntelligenceLayer()
        analytics = PredictiveAnalyticsLayer()
        geoint = GeospatialIntelligenceLayer()
        return {
            "count": len(records),
            "market": analytics.market_summary(records),
            "anomalies": analytics.anomalies(records),
            "geo_clusters": geoint.clusters(records),
            "record_intelligence": [
                {"record_id": record.id, "lead_score": analytics.lead_score(record), **nlp.analyze_record(record)}
                for record in records[:20]
            ],
        }

    @app.post("/api/search")
    async def search(payload: SearchRequest) -> dict[str, Any]:
        policy = PolicyEngine()
        retrieval = RetrievalLayer(policy)
        results = await retrieval.search(payload, await runtime.list_records())
        chain_queries = retrieval.chain_of_retrieval_queries(payload.query)
        if len(results) < max(3, payload.top_k // 4) and len(chain_queries) > 1:
            seen = {item.record.id for item in results}
            expanded_results = []
            for chain_query in chain_queries[1:]:
                expanded_payload = payload.model_copy(update={"query": chain_query})
                for result in await retrieval.search(expanded_payload, await runtime.list_records()):
                    if result.record.id not in seen:
                        seen.add(result.record.id)
                        expanded_results.append(result)
            results = sorted([*results, *expanded_results], key=lambda item: item.score, reverse=True)[: payload.top_k]
        ai = AIApplicationLayer(get_llm_client())
        summary = await ai.summarize_results(payload.query, results)
        return {
            "count": len(results),
            "rerank_requested": policy.should_rerank(payload, len(results)),
            "chain_queries": chain_queries,
            "summary": summary,
            "results": results,
        }

    @app.websocket("/ws/jobs/{job_id}")
    async def job_socket(websocket: WebSocket, job_id: str) -> None:
        await websocket.accept()
        try:
            last_seen: set[str] = set()
            while True:
                events = await runtime.list_events(job_id)
                fresh = [event for event in reversed(events) if event.id not in last_seen]
                for event in fresh:
                    last_seen.add(event.id)
                    await websocket.send_json(event.model_dump(mode="json"))
                await asyncio.sleep(1)
        except WebSocketDisconnect:
            return


async def run_job(job_id: str) -> None:
    job = runtime.jobs.get(job_id)
    if not job:
        return

    settings = get_settings()
    policy = PolicyEngine()
    crawl = CrawlControlPlane()
    compliance = ComplianceLayer(
        settings.default_unknown_domain_delay_seconds,
        settings.domain_token_bucket_capacity,
        settings.domain_token_refill_per_second,
        settings.robots_cache_ttl_hours * 3600,
    )
    proxy_manager = ProxyPoolManager()
    fetcher = FetchLayer(
        enable_network_fetch=settings.enable_network_fetch,
        proxy_manager=proxy_manager,
        browser_pool=ChromiumBrowserPool(pool_size=max(settings.browser_pool_size, 1)),
    )
    discovery = SearchDiscoveryLayer(settings.enable_search_discovery)
    extractor = ExtractionLayer(get_llm_client())
    enrichment = EnrichmentLayer()
    storage = StorageLayer(runtime)
    indexer = IndexingLayer()
    graph = GraphRelationshipEngine()

    try:
        planned_pages = planned_page_count(job.request, settings)
        processed_targets = 0
        skipped_targets = 0
        duplicate_skips = 0
        records_found = 0
        llm_calls = 0
        browser_renders = 0

        # Resolve per-job overrides for network/discovery flags.
        # A job-level True always wins over the global config default.
        effective_network_fetch = (
            job.request.enable_network_fetch
            if job.request.enable_network_fetch is not None
            else settings.enable_network_fetch
        )
        effective_search_discovery = (
            job.request.enable_search_discovery
            if job.request.enable_search_discovery is not None
            else settings.enable_search_discovery
        )

        # Re-instantiate layers with the effective flags so they use the right
        # mode for this specific job.
        fetcher = FetchLayer(
            enable_network_fetch=effective_network_fetch,
            proxy_manager=proxy_manager,
            browser_pool=ChromiumBrowserPool(pool_size=max(settings.browser_pool_size, 1)),
        )
        discovery = SearchDiscoveryLayer(effective_search_discovery)

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
            )
        )
        candidates = [result.candidate for result in discovery_results]
        if not candidates and not effective_search_discovery:
            candidates.extend(crawl.seed_from_query(job.request.query, job.request.location, job.request.limit))
        for candidate in candidates:
            candidate.metadata["allowed_domains"] = job.request.allowed_domains
            candidate.metadata["blocked_domains"] = job.request.blocked_domains
            candidate.metadata["proxy_strategy"] = job.request.proxy_strategy
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

        while (queue or _refill_attempts < _max_refill_attempts) and processed_targets < planned_pages and records_found < job.request.limit:

            # If the queue is empty but we haven't hit the limit yet, try to
            # refill it before giving up.  This is the critical fix for the
            # "scraper stops early" bug: it ensures we keep going even when the
            # initial seed set is exhausted.
            if not queue:
                if _refill_attempts >= _max_refill_attempts:
                    break
                _refill_attempts += 1
                extra_seeds = crawl.seed_from_query(
                    job.request.query, job.request.location, job.request.limit
                )
                extra_seeds += await _discovery_refill(discovery, job.request, planned_pages, queued_urls)
                for seed in crawl.schedule(extra_seeds):
                    key = runtime.url_key(seed.url)
                    if key not in queued_urls:
                        queued_urls.add(key)
                        queue.append(seed)
                if queue:
                    await emit(
                        job_id,
                        LayerName.crawl_control,
                        "frontier_refilled",
                        f"Queue refill #{_refill_attempts}: added {len(queue)} seeds",
                        {"added": len(queue), "records_found": records_found, "limit": job.request.limit},
                    )
                else:
                    # Truly exhausted — nothing more to crawl.
                    break

            candidate = queue.pop(0)
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
                    "Worker stopped before the next page; stored records were kept",
                    {"records_found": records_found, "processed_targets": processed_targets},
                )
                return
            processed_targets += 1

            await runtime.update_job(
                job_id,
                processed_targets=processed_targets,
                skipped_targets=skipped_targets,
                duplicate_skips=duplicate_skips,
                records_found=records_found,
                llm_calls=llm_calls,
                browser_renders=browser_renders,
                current_url=candidate.url,
                progress_message="Checking compliance",
            )

            if job.request.skip_existing and await runtime.has_seen_url(candidate.url):
                skipped_targets += 1
                await runtime.update_job(
                    job_id,
                    skipped_targets=skipped_targets,
                    progress_message="Skipped previously scraped URL",
                )
                await emit(
                    job_id,
                    LayerName.crawl_control,
                    "previously_seen_skip",
                    "URL was scraped in an earlier run and was skipped",
                    {"url": candidate.url},
                )
                continue

            comp = compliance.check(candidate, job.request.allowed_domains, job.request.blocked_domains)
            if not comp.allowed and comp.reason == "domain_rate_limited" and comp.delay_seconds <= 3:
                await asyncio.sleep(comp.delay_seconds)
                comp = compliance.check(candidate, job.request.allowed_domains, job.request.blocked_domains)
            await emit(job_id, LayerName.compliance, "compliance_checked", comp.reason, comp.model_dump())
            if not comp.allowed:
                skipped_targets += 1
                await runtime.update_job(job_id, skipped_targets=skipped_targets, progress_message=f"Skipped: {comp.reason}")
                continue

            decision = policy.decide_for_url(candidate, llm_enabled=job.request.llm_enabled)
            await emit(job_id, LayerName.policy, "decision", "URL routed by policy engine", decision.model_dump())
            if decision.decision == "skip":
                skipped_targets += 1
                await runtime.mark_url_seen(candidate.url)
                await runtime.update_job(job_id, skipped_targets=skipped_targets, progress_message="Skipped by policy")
                continue

            await runtime.update_job(job_id, progress_message="Fetching page")
            fetch = await fetcher.fetch(candidate, decision)
            await runtime.mark_url_seen(candidate.url)
            await emit(job_id, LayerName.fetch, "fetch_complete", "Fetch layer completed", fetch.model_dump(exclude={"html"}))

            if fetch.error == "offline_preview_only":
                skipped_targets += 1
                await runtime.update_job(
                    job_id,
                    skipped_targets=skipped_targets,
                    progress_message="Real network scraping is disabled; preview data was not stored",
                )
                await emit(
                    job_id,
                    LayerName.fetch,
                    "offline_preview_skipped",
                    "Offline preview output is not stored as a business lead",
                    {"url": candidate.url},
                )
                continue

            if fetch.html:
                # Keep remaining_slots relative to the total budget, not the
                # shrinking queue. Without this fix the slot count immediately
                # collapses to 0 and no follow-up URLs are ever added.
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
                        followup.metadata["allowed_domains"] = job.request.allowed_domains
                        followup.metadata["blocked_domains"] = job.request.blocked_domains
                        followup.metadata["proxy_strategy"] = job.request.proxy_strategy
                    new_followups = []
                    for followup in crawl.schedule(followups):
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
                            {"count": len(new_followups), "urls": [item.url for item in new_followups[:12]]},
                        )

            if fetch.error and not fetch.html:
                skipped_targets += 1
                await runtime.update_job(job_id, skipped_targets=skipped_targets, progress_message="Skipped empty fetch result")
                await emit(job_id, LayerName.fetch, "fetch_empty", "Fetch failed and no HTML was available", {"url": candidate.url, "error": fetch.error})
                continue

            await runtime.update_job(job_id, progress_message="Extracting business data")
            extracted = await extractor.extract(fetch, decision, job.request.llm_enabled)
            await emit(
                job_id,
                LayerName.extraction,
                "extract_complete",
                "Extraction cascade completed",
                extracted.model_dump(),
            )
            if not useful_record(extracted):
                skipped_targets += 1
                await runtime.update_job(job_id, skipped_targets=skipped_targets, progress_message="Skipped page with no useful business data")
                await emit(
                    job_id,
                    LayerName.extraction,
                    "no_business_fields",
                    "No email, phone, social profile, or useful business identity was found",
                    extracted.model_dump(),
                )
                continue
            if job.request.require_email and not extracted.email:
                skipped_targets += 1
                await runtime.update_job(job_id, skipped_targets=skipped_targets, progress_message="Skipped page without an email")
                await emit(
                    job_id,
                    LayerName.extraction,
                    "email_required_skip",
                    "Record did not include an email address and email-only mode is enabled",
                    extracted.model_dump(),
                )
                continue

            await runtime.update_job(job_id, progress_message="Enriching and deduping")
            enriched = await enrichment.enrich(extracted, default_city=job.request.location)
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
                records_found += 1
                await emit(job_id, LayerName.storage, "stored", "Record stored", {"record_id": stored_record.id})
            else:
                duplicate_skips += 1
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
                llm_calls += 1
            if decision.fetch_mode.value == "dynamic":
                browser_renders += 1

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


def planned_page_count(request: ScrapeStartRequest, settings: Settings) -> int:
    if request.max_pages:
        return min(request.max_pages, settings.max_job_limit)
    # Multipliers reflect the realistic skip rate: compliance failures, zero-yield
    # pages, duplicates, and offline preview hits all consume a slot without
    # producing a record.  Higher multipliers mean the queue is large enough to
    # reach `limit` even when many pages are skipped.
    multiplier = {
        "fast": 3,       # ~66% efficiency expected
        "balanced": 6,   # ~16% efficiency expected (conservative)
        "deep": 15,      # many deep pages crawled for each record
        "research": 25,  # exhaustive crawl
    }.get(request.mode, 6)
    # Always plan at least limit+10 pages (handles tiny limits gracefully).
    return min(max(request.limit * multiplier, request.limit + 10), settings.max_job_limit)


def useful_record(record: Any) -> bool:
    direct_fields = [
        "email",
        "phone",
        "whatsapp",
        "facebook_url",
        "instagram_url",
        "twitter_url",
        "linkedin_url",
    ]
    if any(getattr(record, field, "") for field in direct_fields):
        return True
    return bool(record.name and (record.website_url or record.address or record.category))


async def _discovery_refill(
    discovery: "SearchDiscoveryLayer",
    request: "ScrapeStartRequest",
    planned_pages: int,
    already_queued: set[str],
) -> "list[URLCandidate]":
    """Generate a fresh batch of discovery seeds when the queue has run dry.

    Uses a slightly different query variant (adding 'contact info') to avoid
    returning URLs that were already seen in the first pass.
    """
    try:
        refill_request = SearchDiscoveryRequest(
            query=f"{request.query} contact info",
            location=request.location,
            max_results=min(max(planned_pages // 2, 10), 200),
        )
        results = await discovery.discover(refill_request)
        return [
            result.candidate
            for result in results
            if runtime.url_key(result.candidate.url) not in already_queued
        ]
    except Exception:
        return []


async def emit(
    job_id: str,
    layer: LayerName,
    event_type: str,
    message: str,
    payload: dict[str, Any] | None = None,
) -> None:
    await runtime.add_event(
        JobEvent(
            job_id=job_id,
            layer=layer,
            event_type=event_type,
            message=message,
            payload=payload or {},
        )
    )


def hydrate_runtime_llm(settings: Settings) -> None:
    if runtime.llm_settings.provider != LLMProvider.disabled or settings.llm_provider == "disabled":
        return
    try:
        provider = LLMProvider(settings.llm_provider)
    except ValueError:
        provider = LLMProvider.disabled
    key = (
        settings.llm_api_key
        or {
            LLMProvider.anthropic: settings.anthropic_api_key,
            LLMProvider.openai: settings.openai_api_key,
            LLMProvider.azure_openai: settings.azure_openai_api_key,
            LLMProvider.google: settings.google_api_key,
            LLMProvider.mistral: settings.mistral_api_key,
            LLMProvider.groq: settings.groq_api_key,
            LLMProvider.together: settings.together_api_key,
            LLMProvider.openrouter: settings.openrouter_api_key,
            LLMProvider.nvidia: settings.nvidia_api_key,
            LLMProvider.deepinfra: settings.deepinfra_api_key,
            LLMProvider.cerebras: settings.cerebras_api_key,
            LLMProvider.fireworks: settings.fireworks_api_key,
            LLMProvider.huggingface: settings.huggingface_api_key,
            LLMProvider.perplexity: settings.perplexity_api_key,
        }.get(provider, "")
    )
    base_url = settings.llm_base_url or (settings.azure_openai_endpoint if provider == LLMProvider.azure_openai else "")
    runtime.llm_settings = LLMSettings(
        provider=provider,
        model=settings.llm_model,
        api_key=SecretStr(key) if key else None,
        base_url=base_url or None,
    )


def normalize_llm_settings(payload: LLMSettings) -> LLMSettings:
    api_key = payload.api_key
    if api_key and not api_key.get_secret_value().strip():
        api_key = None
    existing = runtime.llm_settings
    if (
        api_key is None
        and existing.api_key
        and existing.provider == payload.provider
        and existing.model == payload.model
        and (existing.base_url or "") == (payload.base_url or "")
    ):
        api_key = existing.api_key

    normalized = payload.model_copy(update={"api_key": api_key})
    if normalized.provider == LLMProvider.disabled:
        return normalized.model_copy(update={"api_key": None})
    if normalized.provider == LLMProvider.ollama and not normalized.base_url:
        normalized = normalized.model_copy(update={"base_url": "http://localhost:11434/v1"})
    if normalized.provider in {LLMProvider.openai_compatible, LLMProvider.custom_http}:
        if not normalized.model or not normalized.base_url:
            raise HTTPException(status_code=400, detail="Gateway providers need both Model and Base URL.")
        return normalized
    if normalized.provider == LLMProvider.anthropic and not normalized.base_url:
        normalized = normalized.model_copy(update={"base_url": "https://api.anthropic.com/v1"})
    if normalized.provider != LLMProvider.ollama and not normalized.api_key:
        raise HTTPException(status_code=400, detail="This provider needs an API key. For third-party Claude gateways, choose Independent Claude / OpenAI-Compatible Gateway and set Base URL.")
    if not normalized.model:
        raise HTTPException(status_code=400, detail="Model is required.")
    return normalized


def capability_catalog() -> list[dict[str, Any]]:
    cards = [
        CapabilityCard(key="inverted_index", name="Inverted Index", category="retrieval", status="implemented", practical_use="Fast term postings for candidate generation", source_module="layers.search_index"),
        CapabilityCard(key="tfidf", name="TF-IDF", category="retrieval", status="implemented", practical_use="Interpretable lexical ranking", source_module="layers.search_index"),
        CapabilityCard(key="ann", name="ANN Search", category="retrieval", status="implemented", practical_use="Local LSH buckets; Qdrant HNSW in production", source_module="layers.search_index"),
        CapabilityCard(key="bm25_ltr_hybrid", name="BM25 + LTR + Hybrid Retrieval", category="retrieval", status="implemented", practical_use="RRF fused ranking over lexical, dense, sparse, graph and neural-style signals", source_module="layers.retrieval"),
        CapabilityCard(key="bert_transformer_rag", name="BERT / Transformer / RAG Adapters", category="neural", status="adapter_ready", practical_use="Provider-backed embeddings, reranking, extraction and summaries", source_module="layers.nlp_intelligence"),
        CapabilityCard(key="rlhf_feedback", name="RLHF Feedback Loop", category="neural", status="adapter_ready", practical_use="Operator feedback updates crawl/rank rewards", source_module="layers.policy"),
        CapabilityCard(key="self_healing_scrapers", name="Self-Healing Scrapers", category="scraping", status="implemented", practical_use="CSS, XPath, DOM fingerprint, heuristic, LLM and manual review cascade", source_module="layers.extraction"),
        CapabilityCard(key="dom_css_xpath", name="DOM / CSS / XPath", category="scraping", status="implemented", practical_use="Structured page parsing and selector matching", source_module="layers.dom_tools"),
        CapabilityCard(key="safe_osint", name="Google Dorking / OSINT Fusion", category="osint", status="guarded", safety_boundary="Public business discovery only; blocks credential/session/admin dorks", practical_use="Business source discovery with human review", source_module="layers.osint"),
        CapabilityCard(key="api_sessions", name="API Session Handling", category="osint", status="guarded", safety_boundary="Documented public APIs or owned OAuth only; no exploitation", practical_use="Safe integration with authorized APIs", source_module="layers.osint"),
        CapabilityCard(key="chromium", name="Headless Browser Automation", category="scraping", status="implemented", practical_use="Playwright Chromium rendering behind compliance checks", source_module="layers.browser"),
        CapabilityCard(key="graph", name="Graph / Network Analysis", category="analytics", status="implemented", practical_use="Neo4j-ready competitor, duplicate, same-area and same-network edges", source_module="layers.graph"),
        CapabilityCard(key="vision", name="Computer Vision", category="analytics", status="guarded", safety_boundary="No face identification or biometric recognition", practical_use="Business media labels, OCR adapter, storefront/logo adapter", source_module="layers.vision"),
        CapabilityCard(key="predictive", name="Predictive Analytics / Anomaly Detection", category="analytics", status="implemented", practical_use="Lead scoring, market summary and outlier detection", source_module="layers.analytics"),
        CapabilityCard(key="geoint", name="Geospatial Intelligence", category="analytics", status="implemented", practical_use="Distance, area clustering and proximity duplicate detection", source_module="layers.geoint"),
        CapabilityCard(key="universal_agent", name="Universal Web Agent", category="research", status="guarded", safety_boundary="Compliance checks, confidence thresholds and manual review are mandatory", practical_use="Zero-shot extraction through safe policy/browser/LLM adapters", source_module="layers.ai_app"),
    ]
    return [card.model_dump(mode="json") for card in cards]


app = create_app()
