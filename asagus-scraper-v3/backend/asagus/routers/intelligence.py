"""
Intelligence Router — Search, algorithm state, observability, analytics, and policy.
"""
from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from asagus.config import Settings, get_settings
from asagus.layers.ai_app import AIApplicationLayer
from asagus.layers.analytics import PredictiveAnalyticsLayer
from asagus.layers.antibot_layer6_native import native_layer_runtime_status
from asagus.layers.browser import ChromiumBrowserPool
from asagus.layers.captcha_solver import create_captcha_solver
from asagus.layers.discovery import SearchDiscoveryLayer
from asagus.layers.dom_tools import DOMTools
from asagus.layers.extraction import ExtractionLayer
from asagus.layers.geoint import GeospatialIntelligenceLayer
from asagus.layers.lead_intelligence import adapter_state
from asagus.layers.nlp_intelligence import NLPIntelligenceLayer
from asagus.layers.observability import ObservabilityLayer
from asagus.layers.osint import SafeOSINTLayer
from asagus.layers.proxy import ProxyPoolManager
from asagus.layers.registry import ordered_blueprint_layers
from asagus.layers.search_index import InvertedSearchIndex
from asagus.layers.social_auth import SocialAuthLayer
from asagus.layers.throughput import AsyncCPUHybridExecutor, accelerator_state, resource_profile_for
from asagus.layers.vision import ComputerVisionLayer
from asagus.llm.providers import provider_catalog
from asagus.models import (
    LLMProvider,
    SearchDiscoveryRequest,
    SearchRequest,
    ScrapeStartRequest,
    URLCandidate,
)
from asagus.services.catalog import capability_catalog
from asagus.services.health import collect_health
from asagus.services.job_helpers import antibot_preset_plan, proxy_urls_from_settings
from asagus.services.runtime import runtime
from asagus.routers.deps import get_llm_client, get_services, require_operator

router = APIRouter(prefix="/api", tags=["intelligence"])


@router.get("/blueprint")
async def blueprint() -> dict[str, Any]:
    from asagus import __version__
    return {
        "version": "3.0",
        "source_of_truth": "ASAGUS scrapper _3_0_v2.md",
        "layers": ordered_blueprint_layers(),
    }


@router.get("/providers")
async def providers() -> dict[str, Any]:
    return {"providers": [preset.model_dump(mode="json") for preset in provider_catalog()]}


@router.get("/health")
async def health(settings: Settings = Depends(get_settings)) -> Any:
    return await collect_health(settings)


@router.get("/algorithm/state")
async def algorithm_state(
    settings: Settings = Depends(get_settings),
    services: Any = Depends(get_services),
) -> dict[str, Any]:
    policy = services.policy
    crawl = services.crawl
    compliance = services.compliance
    proxy = ProxyPoolManager(proxy_urls_from_settings(settings))
    graph = services.graph
    observability = ObservabilityLayer()
    nlp = services.nlp
    osint = SafeOSINTLayer()
    dom_tools = DOMTools()
    analytics = PredictiveAnalyticsLayer()
    geoint = GeospatialIntelligenceLayer()
    vision = ComputerVisionLayer()
    throughput = AsyncCPUHybridExecutor(
        resource_profile_for(
            "normal",
            settings_io=settings.crawl_concurrency_limit,
            settings_cpu=settings.cpu_worker_processes,
            settings_queue=settings.pipeline_queue_maxsize,
            settings_browser=settings.browser_pool_size,
        )
    )
    retrieval = services.retrieval
    records = await runtime.list_records()
    index_state = InvertedSearchIndex().build(records).state()
    return {
        "policy": {**policy.stats(), "domains": [state.model_dump(mode="json") for state in policy.domain_states()[:10]]},
        "mdp": crawl.algorithm_state(),
        "compliance": compliance.stats(),
        "browser": ChromiumBrowserPool(
            pool_size=settings.browser_pool_size or 1,
            engine=settings.browser_automation_engine,
            headless=settings.browser_headless,
            camoufox_binary_path=settings.camoufox_binary_path,
        ).state(),
        "captcha_solver": create_captcha_solver().state(),
        "native_layer6": native_layer_runtime_status(),
        "social_auth": SocialAuthLayer(settings, ScrapeStartRequest(query="preview", location="preview")).state(),
        "antibot_presets": {
            preset: antibot_preset_plan(
                ScrapeStartRequest(query="preview", location="preview", antibot_preset=preset),
                settings,
            )
            for preset in ("high-stealth", "balanced", "high-speed")
        },
        "proxy": proxy.state(),
        "discovery": services.discovery.state(),
        "external_adapters": adapter_state(),
        "throughput": throughput.state(),
        "accelerators": accelerator_state(),
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


@router.post("/discovery/search")
async def discovery_search(
    payload: SearchDiscoveryRequest,
    services: Any = Depends(get_services),
) -> dict[str, Any]:
    results = await services.discovery.discover(payload)
    return {"count": len(results), "results": results}


@router.post("/policy/decision")
async def policy_decision(
    candidate: URLCandidate,
    services: Any = Depends(get_services),
) -> Any:
    return services.policy.decide_for_url(
        candidate,
        llm_enabled=runtime.llm_settings.provider != LLMProvider.disabled,
    )


@router.get("/policy/stats")
async def policy_stats(services: Any = Depends(get_services)) -> dict[str, Any]:
    stats = services.policy.stats()
    stats.update(runtime.policy_stats)
    return stats


@router.get("/policy/domains")
async def policy_domains(services: Any = Depends(get_services)) -> dict[str, Any]:
    return {"domains": [state.model_dump(mode="json") for state in services.policy.domain_states()]}


@router.get("/observability")
async def observability(services: Any = Depends(get_services)) -> dict[str, Any]:
    policy = services.policy.stats()
    jobs = await runtime.list_jobs()
    metrics = ObservabilityLayer().from_runtime(jobs, policy)
    return {"metrics": metrics}


@router.get("/intelligence", dependencies=[Depends(require_operator)])
async def intelligence(services: Any = Depends(get_services)) -> dict[str, Any]:
    records = await runtime.list_records()
    nlp = services.nlp
    analytics = PredictiveAnalyticsLayer()
    geoint = GeospatialIntelligenceLayer()
    return {
        "count": len(records),
        "market": analytics.market_summary(records),
        "outreach": analytics.outreach_summary(records),
        "anomalies": analytics.anomalies(records),
        "geo_clusters": geoint.clusters(records),
        "record_intelligence": [
            {
                "record_id": record.id,
                "lead_score": analytics.lead_score(record),
                "outreach_profile": record.raw_fields.get("outreach_profile", {}),
                **nlp.analyze_record(record),
            }
            for record in records[:20]
        ],
    }


@router.post("/search", dependencies=[Depends(require_operator)])
async def search(
    payload: SearchRequest,
    services: Any = Depends(get_services),
) -> dict[str, Any]:
    policy = services.policy
    retrieval = services.retrieval
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


# ─── WebSocket ──────────────────────────────────────────────────────────

@router.websocket("/ws/jobs/{job_id}")
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
