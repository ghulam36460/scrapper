"""
ENV Manager — Safe read/write of .env settings from the API.

Allows the frontend to edit backend configuration (proxy URLs, browser engine,
LLM keys, scraping toggles) and persist them to .env without restarting manually.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from uuid import uuid4

# Allowed keys that can be read/written via the API.
# This whitelist prevents injection of arbitrary shell variables.
_ALLOWED_KEYS: set[str] = {
    # Runtime gates
    "ENABLE_NETWORK_FETCH",
    "ENABLE_SEARCH_DISCOVERY",
    "ENABLE_INFRA_PERSISTENCE",
    "ENVIRONMENT",
    # Browser & automation
    "BROWSER_AUTOMATION_ENGINE",
    "BROWSER_HEADLESS",
    "BROWSER_POOL_SIZE",
    "CAMOUFOX_BINARY_PATH",
    "SOCIAL_AUTH_SESSIONS_DIR",
    "FACEBOOK_STORAGE_STATE_PATH",
    "INSTAGRAM_STORAGE_STATE_PATH",
    # Concurrency & performance
    "CRAWL_CONCURRENCY_LIMIT",
    "CPU_WORKER_PROCESSES",
    "PIPELINE_QUEUE_MAXSIZE",
    "DISCOVERY_CONCURRENCY_LIMIT",
    # LLM settings
    "LLM_PROVIDER",
    "LLM_MODEL",
    "LLM_API_KEY",
    "LLM_BASE_URL",
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "AZURE_OPENAI_API_KEY",
    "AZURE_OPENAI_ENDPOINT",
    "GOOGLE_API_KEY",
    "MISTRAL_API_KEY",
    "GROQ_API_KEY",
    "TOGETHER_API_KEY",
    "OPENROUTER_API_KEY",
    "NVIDIA_API_KEY",
    "DEEPINFRA_API_KEY",
    "CEREBRAS_API_KEY",
    "FIREWORKS_API_KEY",
    "HUGGINGFACE_API_KEY",
    "PERPLEXITY_API_KEY",
    # Proxy
    "RESIDENTIAL_PROXY_URL",
    "ISP_STATIC_PROXY_URL",
    "DATACENTER_PROXY_URL",
    "BUDGET_RESIDENTIAL_PROXY_URL",
    "BRIGHTDATA_USERNAME",
    "BRIGHTDATA_PASSWORD",
    "WEBSHARE_API_KEY",
    "IPROYAL_API_KEY",
    # Security
    "OPERATOR_TOKEN",
    "FRONTEND_ORIGIN",
    # Infrastructure (optional)
    "POSTGRES_URL",
    "REDIS_URL",
    "OPENSEARCH_HOST",
    "QDRANT_HOST",
    "NEO4J_URI",
    "NEO4J_USER",
    "NEO4J_PASSWORD",
    "MINIO_ENDPOINT",
    "MINIO_ACCESS_KEY",
    "MINIO_SECRET_KEY",
    "MINIO_BUCKET",
    # Limits
    "MAX_JOB_LIMIT",
    "DEFAULT_UNKNOWN_DOMAIN_DELAY_SECONDS",
    "ROBOTS_CACHE_TTL_HOURS",
    "LLM_FALLBACK_CACHE_DAYS",
    "DOMAIN_TOKEN_BUCKET_CAPACITY",
    "DOMAIN_TOKEN_REFILL_PER_SECOND",
    # MAX mode
    "MAX_MODE_GPU_ENABLED",
    "MAX_MODE_PARALLELISM",
}

# Keys that contain secrets — mask their values in GET responses
_SECRET_KEYS: set[str] = {
    "LLM_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY",
    "AZURE_OPENAI_API_KEY", "GOOGLE_API_KEY", "MISTRAL_API_KEY",
    "GROQ_API_KEY", "TOGETHER_API_KEY", "OPENROUTER_API_KEY",
    "NVIDIA_API_KEY", "DEEPINFRA_API_KEY", "CEREBRAS_API_KEY",
    "FIREWORKS_API_KEY", "HUGGINGFACE_API_KEY", "PERPLEXITY_API_KEY",
    "BRIGHTDATA_PASSWORD", "WEBSHARE_API_KEY", "IPROYAL_API_KEY",
    "OPERATOR_TOKEN", "RESIDENTIAL_PROXY_URL", "ISP_STATIC_PROXY_URL",
    "DATACENTER_PROXY_URL", "BUDGET_RESIDENTIAL_PROXY_URL",
    "NEO4J_PASSWORD", "MINIO_SECRET_KEY", "MINIO_ACCESS_KEY",
}


def _find_env_path() -> Path:
    """Locate the .env file: try backend/.env then project root .env."""
    candidates = [
        Path(__file__).resolve().parents[3] / ".env",
        Path(__file__).resolve().parents[4] / ".env",
    ]
    for path in candidates:
        if path.exists():
            return path
    # Return the first candidate as the creation target
    return candidates[0]


def _parse_env_file(path: Path) -> dict[str, str]:
    """Parse a .env file into a dict, preserving comments."""
    result: dict[str, str] = {}
    if not path.exists():
        return result
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip().upper()
        value = value.strip().strip('"').strip("'")
        result[key] = value
    return result


def _write_env_file(path: Path, updates: dict[str, str]) -> None:
    """
    Write updates to .env atomically. Preserves existing lines/comments.
    Only keys in updates are modified; other keys are kept as-is.
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    existing_lines: list[str] = []
    if path.exists():
        existing_lines = path.read_text(encoding="utf-8").splitlines()

    written_keys: set[str] = set()
    new_lines: list[str] = []

    for line in existing_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            new_lines.append(line)
            continue
        if "=" not in stripped:
            new_lines.append(line)
            continue
        key = stripped.partition("=")[0].strip().upper()
        if key in updates:
            # Replace existing value
            new_val = updates[key]
            needs_quote = " " in new_val or not new_val
            quoted = f'"{new_val}"' if needs_quote else new_val
            new_lines.append(f"{key}={quoted}")
            written_keys.add(key)
        else:
            new_lines.append(line)

    # Append any new keys that weren't already in the file
    new_entries = [k for k in updates if k not in written_keys]
    if new_entries:
        new_lines.append("")  # blank separator
        new_lines.append("# Added by ASAGUS frontend")
        for key in new_entries:
            val = updates[key]
            needs_quote = " " in val or not val
            quoted = f'"{val}"' if needs_quote else val
            new_lines.append(f"{key}={quoted}")

    tmp_path = path.with_name(f".env.{uuid4().hex[:8]}.tmp")
    try:
        tmp_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
        # os.replace is atomic on POSIX; on Windows retry if the target is locked
        for attempt in range(3):
            try:
                tmp_path.replace(path)
                break
            except PermissionError:
                if attempt == 2:
                    raise
                import time
                time.sleep(0.1 * (attempt + 1))
    except Exception:
        # Clean up temp file on any failure
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass
        raise


def read_env() -> dict[str, Any]:
    """
    Return all allowed .env keys with values.
    Secret keys are masked as '***' unless they are empty.
    """
    path = _find_env_path()
    parsed = _parse_env_file(path)
    result: dict[str, Any] = {}
    for key in sorted(_ALLOWED_KEYS):
        raw = parsed.get(key, "")
        if key in _SECRET_KEYS and raw:
            result[key] = {"value": "***", "set": True}
        else:
            result[key] = {"value": raw, "set": bool(raw)}
    result["_env_path"] = str(path)
    result["_file_exists"] = path.exists()
    return result


def write_env(updates: dict[str, str]) -> dict[str, Any]:
    """
    Write key/value pairs to .env.
    Only whitelisted keys are accepted; others raise ValueError.
    Empty string values are allowed (they clear a setting).
    """
    bad_keys = [k for k in updates if k.upper() not in _ALLOWED_KEYS]
    if bad_keys:
        raise ValueError(f"Not allowed to set: {', '.join(bad_keys)}")

    # Validate values — no shell injection
    for key, value in updates.items():
        if re.search(r'[\r\n\x00]', value):
            raise ValueError(f"Invalid characters in value for {key}")

    normalized = {k.upper(): v for k, v in updates.items()}
    path = _find_env_path()
    _write_env_file(path, normalized)
    return {"ok": True, "updated_keys": list(normalized.keys()), "env_path": str(path)}
