from __future__ import annotations

import json
from typing import Any

import httpx

from asagus.models import ExtractedRecord, ExtractionMethod, LLMProvider, LLMSettings, ProviderPreset


EXTRACTION_SYSTEM_PROMPT = (
    "You extract business lead data from cleaned webpage text. "
    "Return strict JSON only with keys: name, phone, whatsapp, email, address, "
    "city, country_code, website_url, facebook_url, instagram_url, twitter_url, "
    "linkedin_url, category, "
    "confidence. Use empty strings when unknown and confidence from 0 to 1."
)


OPENAI_COMPATIBLE_BASES = {
    LLMProvider.openai: "https://api.openai.com/v1",
    LLMProvider.mistral: "https://api.mistral.ai/v1",
    LLMProvider.groq: "https://api.groq.com/openai/v1",
    LLMProvider.together: "https://api.together.xyz/v1",
    LLMProvider.openrouter: "https://openrouter.ai/api/v1",
    LLMProvider.nvidia: "https://integrate.api.nvidia.com/v1",
    LLMProvider.deepinfra: "https://api.deepinfra.com/v1/openai",
    LLMProvider.cerebras: "https://api.cerebras.ai/v1",
    LLMProvider.fireworks: "https://api.fireworks.ai/inference/v1",
    LLMProvider.huggingface: "https://router.huggingface.co/v1",
    LLMProvider.perplexity: "https://api.perplexity.ai/v1",
    LLMProvider.ollama: "http://localhost:11434/v1",
}


def provider_catalog() -> list[ProviderPreset]:
    return [
        ProviderPreset(
            provider=LLMProvider.anthropic,
            label="Claude / Anthropic",
            default_base_url="https://api.anthropic.com/v1",
            example_models=["claude-opus-4-6", "claude-3-5-sonnet-latest", "claude-3-5-haiku-latest"],
            key_hint="Anthropic API key",
            notes="Uses the Anthropic Messages API. Set Base URL only for an Anthropic-compatible gateway.",
        ),
        ProviderPreset(
            provider=LLMProvider.openai,
            label="OpenAI / ChatGPT",
            default_base_url=OPENAI_COMPATIBLE_BASES[LLMProvider.openai],
            example_models=["gpt-4.1-mini", "gpt-4o-mini"],
            key_hint="OpenAI API key",
        ),
        ProviderPreset(
            provider=LLMProvider.azure_openai,
            label="Azure OpenAI",
            example_models=["deployment-name"],
            key_hint="Azure OpenAI key",
            notes="Set Base URL to your Azure OpenAI resource endpoint; model is the deployment name.",
        ),
        ProviderPreset(
            provider=LLMProvider.google,
            label="Google Gemini",
            example_models=["gemini-2.0-flash", "gemini-1.5-pro"],
            key_hint="Google AI Studio or Vertex-compatible API key",
        ),
        ProviderPreset(
            provider=LLMProvider.mistral,
            label="Mistral",
            default_base_url=OPENAI_COMPATIBLE_BASES[LLMProvider.mistral],
            example_models=["mistral-large-latest", "ministral-8b-latest"],
            key_hint="Mistral API key",
        ),
        ProviderPreset(
            provider=LLMProvider.groq,
            label="Groq",
            default_base_url=OPENAI_COMPATIBLE_BASES[LLMProvider.groq],
            example_models=["llama-3.3-70b-versatile", "llama-3.1-8b-instant"],
            key_hint="Groq API key",
        ),
        ProviderPreset(
            provider=LLMProvider.together,
            label="Together AI",
            default_base_url=OPENAI_COMPATIBLE_BASES[LLMProvider.together],
            example_models=["meta-llama/Llama-3.3-70B-Instruct-Turbo"],
            key_hint="Together API key",
        ),
        ProviderPreset(
            provider=LLMProvider.openrouter,
            label="OpenRouter",
            default_base_url=OPENAI_COMPATIBLE_BASES[LLMProvider.openrouter],
            example_models=["anthropic/claude-3.5-sonnet", "openai/gpt-4o-mini"],
            key_hint="OpenRouter key",
        ),
        ProviderPreset(
            provider=LLMProvider.nvidia,
            label="NVIDIA NIM",
            default_base_url=OPENAI_COMPATIBLE_BASES[LLMProvider.nvidia],
            example_models=["nvidia/llama-3.1-nemotron-nano-8b-v1", "meta/llama-3.1-8b-instruct"],
            key_hint="NVIDIA API key",
            notes="Paste the NVIDIA API key and model only; the NIM gateway URL is filled automatically.",
        ),
        ProviderPreset(
            provider=LLMProvider.deepinfra,
            label="DeepInfra",
            default_base_url=OPENAI_COMPATIBLE_BASES[LLMProvider.deepinfra],
            example_models=["meta-llama/Meta-Llama-3.1-8B-Instruct", "mistralai/Mixtral-8x7B-Instruct-v0.1"],
            key_hint="DeepInfra API key",
        ),
        ProviderPreset(
            provider=LLMProvider.cerebras,
            label="Cerebras",
            default_base_url=OPENAI_COMPATIBLE_BASES[LLMProvider.cerebras],
            example_models=["llama3.1-8b", "llama-3.3-70b"],
            key_hint="Cerebras API key",
        ),
        ProviderPreset(
            provider=LLMProvider.fireworks,
            label="Fireworks AI",
            default_base_url=OPENAI_COMPATIBLE_BASES[LLMProvider.fireworks],
            example_models=["accounts/fireworks/models/llama-v3p1-8b-instruct", "accounts/fireworks/models/qwen2p5-72b-instruct"],
            key_hint="Fireworks API key",
        ),
        ProviderPreset(
            provider=LLMProvider.huggingface,
            label="Hugging Face Router",
            default_base_url=OPENAI_COMPATIBLE_BASES[LLMProvider.huggingface],
            example_models=["meta-llama/Llama-3.1-8B-Instruct", "mistralai/Mistral-7B-Instruct-v0.3"],
            key_hint="Hugging Face token",
            notes="Uses Hugging Face's OpenAI-compatible chat router.",
        ),
        ProviderPreset(
            provider=LLMProvider.perplexity,
            label="Perplexity Sonar",
            default_base_url=OPENAI_COMPATIBLE_BASES[LLMProvider.perplexity],
            example_models=["sonar", "sonar-pro"],
            key_hint="Perplexity API key",
            notes="OpenAI-compatible chat API. Best for summaries; extraction still uses strict JSON prompts.",
        ),
        ProviderPreset(
            provider=LLMProvider.openai_compatible,
            label="Independent Claude / OpenAI-Compatible Gateway",
            example_models=["anthropic/claude-opus-4.6", "claude-opus-4-6", "provider/model-id"],
            key_hint="Gateway API key",
            notes="Use this for third-party Claude, OpenRouter-like, LiteLLM, vLLM, LM Studio, and private /v1 chat gateways.",
        ),
        ProviderPreset(
            provider=LLMProvider.ollama,
            label="Ollama / Local",
            default_base_url=OPENAI_COMPATIBLE_BASES[LLMProvider.ollama],
            example_models=["llama3.1", "qwen2.5"],
            key_hint="No key required for default local Ollama",
            local_only=True,
        ),
        ProviderPreset(
            provider=LLMProvider.custom_http,
            label="Custom HTTP JSON",
            example_models=["custom-model"],
            key_hint="Optional bearer token",
            notes="POSTs OpenAI-style chat JSON to Base URL, useful for private or self-hosted LLM routers.",
        ),
    ]


class LLMClient:
    """Provider-agnostic LLM client for user-supplied keys and local models."""

    def __init__(self, settings: LLMSettings) -> None:
        self.settings = settings

    @property
    def enabled(self) -> bool:
        if self.settings.provider == LLMProvider.disabled:
            return False
        if self.settings.provider == LLMProvider.ollama:
            return bool(self.settings.model)
        if self.settings.provider in {LLMProvider.openai_compatible, LLMProvider.custom_http}:
            return bool(self.settings.model and self.settings.base_url)
        return bool(self.settings.api_key and self.settings.api_key.get_secret_value() and self.settings.model)

    async def extract_business(self, text: str, source_url: str) -> ExtractedRecord | None:
        if not self.enabled:
            return None
        payload = await self._complete_json(
            system=EXTRACTION_SYSTEM_PROMPT,
            user=f"Source URL: {source_url}\n\nContent:\n{text[:12000]}",
        )
        if not payload:
            return None
        return ExtractedRecord(
            source_url=source_url,
            name=str(payload.get("name", "")),
            phone=str(payload.get("phone", "")),
            whatsapp=str(payload.get("whatsapp", "")),
            email=str(payload.get("email", "")),
            address=str(payload.get("address", "")),
            city=str(payload.get("city", "")),
            country_code=str(payload.get("country_code", ""))[:2].upper(),
            website_url=str(payload.get("website_url", "")),
            facebook_url=str(payload.get("facebook_url", "")),
            instagram_url=str(payload.get("instagram_url", "")),
            twitter_url=str(payload.get("twitter_url", "")),
            linkedin_url=str(payload.get("linkedin_url", "")),
            category=str(payload.get("category", "")),
            raw_fields={"llm_provider": self.settings.provider.value, "llm_model": self.settings.model},
            method=ExtractionMethod.llm,
            confidence=max(0.0, min(1.0, float(payload.get("confidence") or 0.55))),
        )

    async def summarize(self, query: str, rows: list[dict[str, Any]]) -> str:
        if not self.enabled:
            return ""
        payload = await self._complete_json(
            system="Summarize lead search results. Return JSON only: {\"summary\":\"...\"}.",
            user=f"Query: {query}\nRows:\n{json.dumps(rows, ensure_ascii=False)[:12000]}",
        )
        return str((payload or {}).get("summary", ""))

    async def _complete_json(self, system: str, user: str) -> dict[str, Any] | None:
        try:
            if self.settings.provider == LLMProvider.anthropic:
                return await self._anthropic_json(system, user)
            if self.settings.provider == LLMProvider.google:
                return await self._google_json(system, user)
            if self.settings.provider == LLMProvider.azure_openai:
                return await self._azure_openai_json(system, user)
            return await self._openai_compatible_json(system, user)
        except Exception:
            return None

    async def _anthropic_json(self, system: str, user: str) -> dict[str, Any] | None:
        key = self._key()
        headers = {
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
            **self.settings.extra_headers,
        }
        body = {
            "model": self.settings.model,
            "system": system,
            "messages": [{"role": "user", "content": user}],
            "max_tokens": 1400,
            "temperature": self.settings.temperature,
        }
        endpoint = (self.settings.base_url or "https://api.anthropic.com/v1").rstrip("/")
        if endpoint.endswith("/messages"):
            url = endpoint
        else:
            url = f"{endpoint}/messages"
        async with httpx.AsyncClient(timeout=self.settings.timeout_seconds) as client:
            response = await client.post(url, headers=headers, json=body)
            response.raise_for_status()
        data = response.json()
        text = "".join(part.get("text", "") for part in data.get("content", []) if part.get("type") == "text")
        return self._parse_json_text(text)

    async def _google_json(self, system: str, user: str) -> dict[str, Any] | None:
        key = self._key()
        endpoint = (self.settings.base_url or "https://generativelanguage.googleapis.com/v1beta").rstrip("/")
        url = f"{endpoint}/models/{self.settings.model}:generateContent?key={key}"
        body = {
            "contents": [{"role": "user", "parts": [{"text": f"{system}\n\n{user}"}]}],
            "generationConfig": {
                "temperature": self.settings.temperature,
                "response_mime_type": "application/json",
            },
        }
        async with httpx.AsyncClient(timeout=self.settings.timeout_seconds) as client:
            response = await client.post(url, headers={"content-type": "application/json", **self.settings.extra_headers}, json=body)
            response.raise_for_status()
        data = response.json()
        parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
        text = "".join(part.get("text", "") for part in parts)
        return self._parse_json_text(text)

    async def _azure_openai_json(self, system: str, user: str) -> dict[str, Any] | None:
        if not self.settings.base_url:
            return None
        endpoint = self.settings.base_url.rstrip("/")
        url = f"{endpoint}/openai/deployments/{self.settings.model}/chat/completions?api-version=2024-10-21"
        headers = {"api-key": self._key(), "content-type": "application/json", **self.settings.extra_headers}
        body = self._chat_body(system, user)
        async with httpx.AsyncClient(timeout=self.settings.timeout_seconds) as client:
            response = await client.post(url, headers=headers, json=body)
            response.raise_for_status()
        return self._parse_openai_response(response.json())

    async def _openai_compatible_json(self, system: str, user: str) -> dict[str, Any] | None:
        base_url = self.settings.base_url or OPENAI_COMPATIBLE_BASES.get(self.settings.provider, "")
        if not base_url:
            return None
        url = base_url.rstrip("/")
        if not url.endswith("/chat/completions"):
            url = f"{url}/chat/completions"
        headers = {"content-type": "application/json", **self.settings.extra_headers}
        key = self._key()
        if key:
            headers["authorization"] = f"Bearer {key}"
        body = self._chat_body(system, user, json_mode=True)
        async with httpx.AsyncClient(timeout=self.settings.timeout_seconds) as client:
            response = await client.post(url, headers=headers, json=body)
            if response.status_code in {400, 404, 422}:
                fallback = await client.post(url, headers=headers, json=self._chat_body(system, user, json_mode=False))
                if fallback.status_code < 400:
                    response = fallback
            response.raise_for_status()
        return self._parse_openai_response(response.json())

    def _chat_body(self, system: str, user: str, json_mode: bool = True) -> dict[str, Any]:
        body = {
            "model": self.settings.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": self.settings.temperature,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        return body

    def _parse_openai_response(self, data: dict[str, Any]) -> dict[str, Any] | None:
        text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return self._parse_json_text(text)

    def _parse_json_text(self, text: str) -> dict[str, Any] | None:
        text = (text or "").strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:].strip()
        try:
            parsed = json.loads(text)
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start >= 0 and end > start:
                try:
                    parsed = json.loads(text[start : end + 1])
                    return parsed if isinstance(parsed, dict) else None
                except json.JSONDecodeError:
                    return None
        return None

    def _key(self) -> str:
        return self.settings.api_key.get_secret_value() if self.settings.api_key else ""
