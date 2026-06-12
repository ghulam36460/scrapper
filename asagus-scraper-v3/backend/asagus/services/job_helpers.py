from __future__ import annotations

import asyncio
import json
import re
from typing import Any
from urllib.parse import urlparse

from asagus.config import Settings, get_settings
from asagus.models import (
    ExtractedRecord,
    ExtractionMethod,
    JobEvent,
    LayerName,
    MDPAction,
    ProxyTier,
    ScrapeStartRequest,
    SearchDiscoveryRequest,
    ThroughputProfile,
    URLCandidate,
)
from asagus.services.runtime import runtime


def planned_page_count(request: ScrapeStartRequest, settings: Settings) -> int:
    if request.max_pages:
        return min(request.max_pages, settings.max_job_limit)
    multiplier = {
        "fast": 3,
        "focused": 4,
        "balanced": 6,
        "adaptive": 8,
        "deep": 15,
        "deep_agent": 18,
        "parallel": 10,
        "comprehensive": 30,
        "research": 25,
        "max": 50,  # MAX mode: broadest possible frontier
    }.get(request.mode, 6)
    if request.discovery_mode in {"social_first", "social_only"}:
        multiplier = max(multiplier, 10)
    return min(max(request.limit * multiplier, request.limit + 10), settings.max_job_limit)


SOCIAL_PROFILE_HOSTS = ("facebook.com", "fb.com", "instagram.com", "x.com", "twitter.com", "linkedin.com")
LOCAL_PLATFORM_HOSTS = (
    "google.",
    "yelp.",
    "tripadvisor.",
    "foursquare.",
    "yellowpages.",
)


def effective_website_filter(request: ScrapeStartRequest) -> str:
    if request.discovery_mode == "social_only":
        return "no_website"
    return request.website_filter


def effective_runtime_flags(request: ScrapeStartRequest, settings: Settings) -> tuple[bool, bool]:
    return (
        request.enable_network_fetch if request.enable_network_fetch is not None else settings.enable_network_fetch,
        request.enable_search_discovery
        if request.enable_search_discovery is not None
        else settings.enable_search_discovery,
    )


def antibot_preset_plan(request: ScrapeStartRequest, settings: Settings) -> dict[str, Any]:
    """Resolve the per-job research preset into the browser/client path."""
    preset_map: dict[str, dict[str, Any]] = {
        "high-stealth": {
            "browser_engine": "camoufox",
            "static_client": "curl_cffi_chrome_impersonation",
            "behavioral_simulation": True,
            "native_layer_requested": True,
            "challenge_bypass": False,
            "notes": "Prefer Camoufox when installed; falls back to Playwright for research reproducibility.",
        },
        "balanced": {
            "browser_engine": "patchright",
            "static_client": "curl_cffi_chrome_impersonation",
            "behavioral_simulation": False,
            "native_layer_requested": False,
            "challenge_bypass": False,
            "notes": "Prefer Patchright when installed; falls back to Playwright if optional packages are unavailable.",
        },
        "high-speed": {
            "browser_engine": "playwright",
            "static_client": "curl_cffi_chrome_impersonation",
            "behavioral_simulation": False,
            "native_layer_requested": False,
            "challenge_bypass": False,
            "notes": "Use the fastest local renderer plus static HTTP impersonation; no native patching is attempted.",
        },
        # MAX mode preset: everything enabled, all layers active
        "max": {
            "browser_engine": "camoufox",
            "static_client": "curl_cffi_chrome_impersonation",
            "behavioral_simulation": True,
            "native_layer_requested": True,
            "challenge_bypass": False,
            "layer6_native": True,
            "gpu_acceleration": True,
            "all_layers": True,
            "max_parallelism": True,
            "nodriver_fallback": True,
            "scrapy_spider": True,
            "download_tools_enabled": True,
            "notes": "MAX mode: all resources, all layers, GPU if available, maximum stealth and parallelism. For research only.",
        },
    }
    # If mode is max, force the max preset
    preset_key = request.antibot_preset
    if request.mode == "max":
        preset_key = "max"
    plan = dict(preset_map.get(preset_key, preset_map["balanced"]))
    if settings.browser_automation_engine != "playwright":
        plan["browser_engine"] = settings.browser_automation_engine
        plan["operator_engine_override"] = settings.browser_automation_engine
    plan["preset"] = preset_key
    plan["scope"] = "educational_research"
    plan["manual_review_on_challenge"] = request.manual_review_on_challenge
    return plan


def mode_plan(request: ScrapeStartRequest, profile: ThroughputProfile, antibot_plan: dict[str, Any] | None = None) -> dict[str, Any]:
    deep_like = request.mode in {"deep", "deep_agent", "comprehensive", "research", "max"}
    parallel_like = request.mode in {"parallel", "max"}
    max_mode = request.mode == "max"
    antibot_plan = antibot_plan or {}
    base_multiplier = {
        "fast": 3,
        "focused": 4,
        "balanced": 6,
        "adaptive": 8,
        "deep": 15,
        "deep_agent": 18,
        "parallel": 10,
        "comprehensive": 30,
        "research": 25,
        "max": 50,
    }.get(request.mode, 6)
    return {
        "mode": request.mode,
        "discovery_mode": request.discovery_mode,
        "lead_target": request.lead_target,
        "website_filter": request.website_filter,
        "decision_maker_titles": request.decision_maker_titles,
        "recipe_set": request.recipe_set,
        "deep_features": {
            "dom_fingerprint": request.capture_dom_fingerprint,
            "device_stamp": request.capture_device_stamp,
            "manual_review_on_challenge": request.manual_review_on_challenge,
            "screenshot_on_failure": request.screenshot_on_failure,
            "browser_action_budget": request.max_browser_actions if request.mode in {"deep_agent", "max"} else 0,
            "browser_action_execution": "planned_guarded" if request.mode in {"deep_agent", "max"} else "not_used",
        },
        "limits": {
            "max_seconds_per_page": request.max_seconds_per_page,
            "max_pages_per_domain": request.max_pages_per_domain or "unlimited",
            "planned_page_multiplier": base_multiplier,
        },
        "resource_profile": "high" if max_mode else request.resource_profile,
        "social_auth": {
            "mode": request.social_auth_mode,
            "platforms": [
                platform.value if hasattr(platform, "value") else str(platform)
                for platform in (
                    request.social_auth_platforms
                    if request.social_auth_mode == "authenticated"
                    else []
                )
            ],
            "session_label": request.social_auth_session_label,
            "required": request.social_auth_required,
            "session_isolation": "platform_scoped_browser_context",
            "password_storage": False,
            "challenge_bypass": False,
        },
        "parallelism": {
            "enabled": parallel_like,
            "io_concurrency": profile.io_concurrency * (2 if max_mode else 1),
            "cpu_workers": profile.cpu_workers * (2 if max_mode else 1),
            "browser_contexts": profile.browser_contexts * (2 if max_mode else 1),
            "queue_maxsize": profile.queue_maxsize,
            "backpressure_policy": profile.backpressure_policy,
        },
        "max_mode_features": {
            "enabled": max_mode,
            "gpu_acceleration": max_mode,
            "all_layers_active": max_mode,
            "layer6_native_binaries": max_mode,
            "download_tools_integration": max_mode,
            "super_stealth": max_mode,
            "max_concurrency": max_mode,
            "nodriver_enabled": max_mode,
            "scrapy_enabled": max_mode,
            "behavioral_simulation": max_mode,
        } if max_mode else {"enabled": False},
        "safety": {
            "challenge_bypass": bool(antibot_plan.get("challenge_bypass", False)),
            "anti_bot_evasion": False,
            "real_browser_per_job_override": True,
            "manual_review_required_for_challenges": request.manual_review_on_challenge,
            "scope": "educational_research",
        },
        "antibot_preset": antibot_plan,
        "deep_mode": deep_like,
    }


def proxy_urls_from_settings(settings: Settings) -> dict[ProxyTier, str]:
    return {
        ProxyTier.residential: settings.residential_proxy_url,
        ProxyTier.isp_static: settings.isp_static_proxy_url,
        ProxyTier.datacenter: settings.datacenter_proxy_url,
        ProxyTier.budget_residential: settings.budget_residential_proxy_url,
    }


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
    raw_fields = getattr(record, "raw_fields", {}) or {}
    if raw_fields.get("decision_makers"):
        return True
    return bool(
        record.name
        and (
            record.website_url
            or record.address
            or record.category
            or record.city
            or record.country_code
            or record.rating is not None
            or record.review_count is not None
        )
    )


def partial_record(record: Any) -> bool:
    if useful_record(record):
        return True
    raw_fields = getattr(record, "raw_fields", {}) or {}
    return bool(
        record.source_url
        and (
            record.name
            or raw_fields.get("links_found", 0)
            or raw_fields.get("content_type")
            or raw_fields.get("status_code")
        )
    )


def website_filter_allows(record: Any, website_filter: str) -> bool:
    has_website = bool(getattr(record, "website_url", ""))
    if website_filter == "has_website":
        return has_website
    if website_filter == "no_website":
        return not has_website
    return True


def social_or_local_platform_url(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    return any(domain in host for domain in (*SOCIAL_PROFILE_HOSTS, *LOCAL_PLATFORM_HOSTS))


def candidate_partial_record(candidate: URLCandidate, request: ScrapeStartRequest, reason: str) -> ExtractedRecord | None:
    if not request.store_partial_records:
        return None
    if effective_website_filter(request) != "no_website" and request.discovery_mode != "social_only":
        return None
    if not social_or_local_platform_url(candidate.url):
        return None

    parsed = urlparse(candidate.url)
    host = parsed.netloc.lower()
    social_fields = {
        "facebook_url": candidate.url if "facebook.com" in host or "fb.com" in host else "",
        "instagram_url": candidate.url if "instagram.com" in host else "",
        "twitter_url": candidate.url if "x.com" in host or "twitter.com" in host else "",
        "linkedin_url": candidate.url if "linkedin.com" in host else "",
    }
    source = "google_maps" if "google." in host and "/maps" in parsed.path.lower() else "directory" if any(
        domain in host for domain in LOCAL_PLATFORM_HOSTS
    ) else "manual"
    name = _candidate_display_name(candidate, request)
    confidence = 0.52 if any(social_fields.values()) else 0.46
    return ExtractedRecord(
        source_url=candidate.url,
        source=source,
        name=name,
        city=request.location,
        category=request.query,
        website_url="",
        raw_fields={
            "partial_record": True,
            "partial_reason": reason,
            "no_owned_website_target": True,
            "candidate_url_type": candidate.url_type.value if hasattr(candidate.url_type, "value") else str(candidate.url_type),
            "candidate_source": candidate.source,
            "candidate_priority": candidate.priority,
            "candidate_metadata": candidate.metadata,
        },
        method=ExtractionMethod.structural_heuristic,
        confidence=confidence,
        **social_fields,
    )


def merge_candidate_partial_record(record: Any, candidate: URLCandidate, request: ScrapeStartRequest, reason: str) -> Any:
    fallback = candidate_partial_record(candidate, request, reason)
    if not fallback:
        return record
    raw_fields = {
        **getattr(record, "raw_fields", {}),
        **fallback.raw_fields,
        "partial_reason": reason,
    }
    updates = {
        "name": getattr(record, "name", "") or fallback.name,
        "city": getattr(record, "city", "") or fallback.city,
        "category": getattr(record, "category", "") or fallback.category,
        "website_url": "",
        "facebook_url": getattr(record, "facebook_url", "") or fallback.facebook_url,
        "instagram_url": getattr(record, "instagram_url", "") or fallback.instagram_url,
        "twitter_url": getattr(record, "twitter_url", "") or fallback.twitter_url,
        "linkedin_url": getattr(record, "linkedin_url", "") or fallback.linkedin_url,
        "raw_fields": raw_fields,
        "confidence": max(getattr(record, "confidence", 0.0), fallback.confidence),
    }
    return record.model_copy(update=updates)


def _candidate_display_name(candidate: URLCandidate, request: ScrapeStartRequest) -> str:
    metadata_name = str(candidate.metadata.get("title") or candidate.metadata.get("business_name") or "").strip()
    if metadata_name:
        return metadata_name[:160]
    parsed = urlparse(candidate.url)
    path = parsed.path.strip("/")
    if "google." in parsed.netloc.lower() and "/maps" in parsed.path.lower():
        path = parsed.path.rsplit("/", 1)[-1]
    slug = path or parsed.netloc
    slug = re.sub(r"[-_+%]+", " ", slug)
    slug = re.sub(r"\s+", " ", slug).strip(" /")
    if slug:
        return slug.title()[:160]
    return f"{request.query.title()} in {request.location}".strip()


async def discovery_refill(
    discovery: Any,
    request: ScrapeStartRequest,
    planned_pages: int,
    already_queued: set[str],
    attempt: int = 1,
) -> list[URLCandidate]:
    try:
        variants = [
            f"{request.query} contact info",
            f"{request.query} official website phone email",
            f"{request.query} locations branches social profiles",
        ]
        if effective_website_filter(request) == "no_website":
            variants = [
                f"{request.query} no website facebook instagram whatsapp phone",
                f"{request.query} {request.location} facebook instagram",
                f"{request.query} {request.location} maps profile phone whatsapp",
                f"{request.query} {request.location} directory phone no website",
            ]
        if request.discovery_mode in {"social_first", "social_only"}:
            variants = [
                f"{request.query} {request.location} facebook instagram whatsapp phone",
                f"{request.query} {request.location} google maps facebook instagram",
                f"{request.query} {request.location} directory phone no website",
            ]
            if effective_website_filter(request) == "no_website":
                variants = [
                    f"{request.query} {request.location} facebook instagram whatsapp",
                    f"{request.query} {request.location} site:facebook.com OR site:instagram.com",
                    f"{request.query} {request.location} google maps phone",
                    f"{request.query} {request.location} phone whatsapp no website",
                ]
        if request.lead_target == "decision_makers":
            variants = [
                f"{request.query} {request.decision_maker_titles} email facebook linkedin",
                f"{request.query} owner founder CEO small business contact",
                f"{request.query} site:linkedin.com/in OR site:facebook.com owner founder",
            ]
        query = variants[min(max(attempt, 1), len(variants)) - 1]
        refill_request = SearchDiscoveryRequest(
            query=query,
            location=request.location,
            max_results=min(max(planned_pages // 2, 10), 200),
            discovery_mode=request.discovery_mode,
            lead_target=request.lead_target,
            website_filter=effective_website_filter(request),
            decision_maker_titles=request.decision_maker_titles,
        )
        results = await discovery.discover(refill_request)
        return [
            result.candidate
            for result in results
            if runtime.url_key(result.candidate.url) not in already_queued
        ]
    except Exception:
        return []


async def sleep_or_cancel(job_id: str, seconds: float) -> bool:
    deadline = max(0.0, seconds)
    slept = 0.0
    while slept < deadline:
        current = runtime.jobs.get(job_id)
        if current and current.status.value == "cancelled":
            await emit(job_id, LayerName.ai_app, "job_cancelled", "Job cancelled during crawl pacing")
            return False
        step = min(1.0, deadline - slept)
        await asyncio.sleep(step)
        slept += step
    return True


async def emit(
    job_id: str,
    layer: LayerName,
    event_type: str,
    message: str,
    payload: dict[str, Any] | None = None,
) -> None:
    event = JobEvent(
        job_id=job_id,
        layer=layer,
        event_type=event_type,
        message=message,
        payload=payload or {},
    )
    await runtime.add_event(event)
    settings = get_settings()
    if not settings.enable_infra_persistence:
        return
    try:
        import redis.asyncio as redis

        client = redis.from_url(settings.redis_url, socket_connect_timeout=1, socket_timeout=1)
        try:
            await client.xadd(
                "asagus:job-events",
                {
                    "job_id": event.job_id,
                    "layer": event.layer.value,
                    "event_type": event.event_type,
                    "message": event.message,
                    "payload": json.dumps(event.payload, ensure_ascii=False),
                    "created_at": event.created_at.isoformat(),
                },
                maxlen=10_000,
                approximate=True,
            )
        finally:
            await client.aclose()
    except Exception:
        return


def domain_from_url(url: str) -> str:
    return urlparse(url).netloc.lower()
