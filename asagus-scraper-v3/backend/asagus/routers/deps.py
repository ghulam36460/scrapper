"""
Shared dependencies for all ASAGUS API routers.

Provides authentication, service injection, and common utilities
used across all router modules.
"""
from __future__ import annotations

from typing import Any

from fastapi import Depends, Header, HTTPException, Request

from asagus.config import Settings, get_settings
from asagus.llm.providers import LLMClient
from asagus.models import LLMProvider
from asagus.services.runtime import runtime


# ─── Forward reference to avoid circular imports ────────────────────────────
# AppServices is defined in main.py; routers access it via request.app.state
def get_services(request: Request) -> Any:
    """Inject the AppServices singleton from app state."""
    return request.app.state.services


def get_llm_client() -> LLMClient | None:
    """Build an LLM client from current runtime settings, or None if disabled."""
    if runtime.llm_settings.provider == LLMProvider.disabled:
        return None
    return LLMClient(runtime.llm_settings)


async def require_operator(
    authorization: str = Header(default=""),
    settings: Settings = Depends(get_settings),
) -> None:
    """
    Dependency that enforces operator-token authentication.

    If OPERATOR_TOKEN is not set in the backend config, access is open.
    Otherwise the caller must supply `Authorization: Bearer <token>`.
    """
    if not settings.operator_token:
        return
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or token != settings.operator_token:
        raise HTTPException(status_code=401, detail="Operator token required")
