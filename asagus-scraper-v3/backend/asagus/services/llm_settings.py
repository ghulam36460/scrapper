from __future__ import annotations

from fastapi import HTTPException
from pydantic import SecretStr

from asagus.config import Settings
from asagus.models import LLMProvider, LLMSettings
from asagus.services.runtime import runtime


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
