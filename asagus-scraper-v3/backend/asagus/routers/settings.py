"""
Settings Router — LLM configuration, ENV management, and runtime mode.

Security hardening:
- ENV writes validated and rate limited
- Value lengths capped
- Audit logging on env changes
"""
from __future__ import annotations

import logging
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from asagus.config import Settings, get_settings
from asagus.models import LLMProvider, LLMSettings
from asagus.services.env_manager import read_env, write_env
from asagus.services.llm_settings import normalize_llm_settings
from asagus.services.runtime import runtime
from asagus.routers.deps import get_llm_client, require_operator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["settings"])

# ─── ENV write rate limiting ────────────────────────────────────────────
_env_write_timestamps: list[float] = []
_MAX_ENV_WRITES_PER_MINUTE = 10
_MAX_ENV_VALUE_LENGTH = 2048


def _check_env_rate_limit() -> None:
    """Enforce max env writes per minute."""
    now = time.time()
    while _env_write_timestamps and _env_write_timestamps[0] < now - 60:
        _env_write_timestamps.pop(0)
    if len(_env_write_timestamps) >= _MAX_ENV_WRITES_PER_MINUTE:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limited: max {_MAX_ENV_WRITES_PER_MINUTE} env writes per minute",
        )
    _env_write_timestamps.append(now)


# ─── LLM Settings ──────────────────────────────────────────────────────

@router.get("/llm/settings")
async def get_llm_settings() -> dict[str, Any]:
    return runtime.llm_settings.masked()


@router.post("/llm/settings", dependencies=[Depends(require_operator)])
async def set_llm_settings(payload: LLMSettings) -> dict[str, Any]:
    """✅ FIX #6: Enhanced LLM settings with validation."""
    # Validate provider-specific requirements
    if payload.provider != LLMProvider.disabled:
        if not payload.model:
            raise HTTPException(
                status_code=400,
                detail=f"Model name is required for provider {payload.provider.value}"
            )
        
        # Validate API key requirements
        providers_requiring_key = {
            LLMProvider.anthropic,
            LLMProvider.openai,
            LLMProvider.azure_openai,
            LLMProvider.google,
            LLMProvider.mistral,
            LLMProvider.groq,
            LLMProvider.together,
            LLMProvider.openrouter,
            LLMProvider.nvidia,
            LLMProvider.deepinfra,
            LLMProvider.cerebras,
            LLMProvider.fireworks,
            LLMProvider.huggingface,
            LLMProvider.perplexity,
        }
        
        if payload.provider in providers_requiring_key and not payload.api_key:
            raise HTTPException(
                status_code=400,
                detail=f"API key is required for provider {payload.provider.value}"
            )
        
        # Validate base URL for providers that need it
        if payload.provider == LLMProvider.azure_openai and not payload.base_url:
            raise HTTPException(
                status_code=400,
                detail="Base URL (Azure OpenAI endpoint) is required for Azure provider"
            )
        
        if payload.provider in {LLMProvider.ollama, LLMProvider.openai_compatible} and not payload.base_url:
            raise HTTPException(
                status_code=400,
                detail=f"Base URL is required for provider {payload.provider.value}"
            )
    
    runtime.llm_settings = normalize_llm_settings(payload)
    runtime.persist_llm_settings()
    
    logger.info(f"[AUDIT] LLM settings updated: provider={payload.provider.value}, model={payload.model}")
    
    return runtime.llm_settings.masked()


@router.post("/llm/test", dependencies=[Depends(require_operator)])
async def test_llm_settings() -> dict[str, Any]:
    client = get_llm_client()
    if not client:
        return {
            "ok": False,
            "provider": runtime.llm_settings.provider.value,
            "model": runtime.llm_settings.model,
            "enabled": False,
            "message": "LLM provider is disabled.",
        }
    ok, message = await client.test_connection()
    return {
        "ok": ok,
        "provider": runtime.llm_settings.provider.value,
        "model": runtime.llm_settings.model,
        "enabled": client.enabled,
        "message": message,
    }


# ─── Runtime Mode ──────────────────────────────────────────────────────

@router.get("/runtime/mode")
async def runtime_mode(settings: Settings = Depends(get_settings)) -> dict[str, Any]:
    return {
        "environment": settings.environment,
        "auth_required": bool(settings.operator_token),
        "network_fetch_enabled": settings.enable_network_fetch,
        "search_discovery_enabled": settings.enable_search_discovery,
        "per_job_controls": {
            "network_fetch": "can_override",
            "search_discovery": "can_override",
        },
        "modes": {
            "fast": "static-first, low page multiplier",
            "balanced": "default scheduler and extraction cascade",
            "focused": "targeted crawl with a modest page multiplier",
            "adaptive": "balanced crawl with expanded refill budget",
            "deep": "larger frontier with dynamic render allowed by policy",
            "deep_agent": "deep crawl budget with DOM stamps, challenge review and recipe metadata",
            "parallel": "resource-governed higher concurrency profile",
            "comprehensive": "broadest non-research crawl budget",
            "research": "largest frontier and trace-heavy review mode",
            "max": "🚀 MAX MODE: all layers, all resources, GPU if available, super stealth, max parallelism, all Download tools active — for advanced research only",
        },
        "resource_profiles": {
            "low": "CPU-friendly, fewer browser contexts",
            "normal": "balanced for local Linux machines",
            "high": "higher queue and I/O limits, still capped by backend settings",
        },
        "message": "Real network discovery/fetch is currently enabled by default for educational research runs, but can be overridden per job.",
    }


# ─── ENV Settings (Hardened) ────────────────────────────────────────────

@router.get("/env/settings", dependencies=[Depends(require_operator)])
async def get_env_settings() -> dict[str, Any]:
    """Read current .env settings (secrets are masked)."""
    return read_env()


@router.post("/env/settings", dependencies=[Depends(require_operator)])
async def update_env_settings(payload: dict[str, str]) -> dict[str, Any]:
    """
    Write key/value pairs to .env.

    Security measures:
    - Only whitelisted keys accepted (enforced by env_manager)
    - Value lengths capped at 2048 chars
    - Rate limited to 10 writes per minute
    - All changes audit logged
    """
    _check_env_rate_limit()

    # Validate value lengths
    for key, value in payload.items():
        if len(value) > _MAX_ENV_VALUE_LENGTH:
            raise HTTPException(
                status_code=400,
                detail=f"Value for {key} too long (max {_MAX_ENV_VALUE_LENGTH} chars)",
            )

    logger.info(f"[AUDIT] ENV settings update: keys={list(payload.keys())}")

    try:
        result = write_env(payload)
        logger.info(f"[AUDIT] ENV settings written: updated_keys={result.get('updated_keys')}")
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
