from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "ASAGUS Scraper 3.0"
    environment: Literal["local", "staging", "production"] = "local"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    frontend_origin: str = "http://localhost:3000"

    postgres_url: str = "postgresql://asagus:asagus@localhost:5432/asagus"
    redis_url: str = "redis://localhost:6379/0"
    opensearch_host: str = "http://localhost:9200"
    qdrant_host: str = "http://localhost:6333"
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "asagus-graph"
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "asagus-access"
    minio_secret_key: str = "asagus-secret"
    minio_bucket: str = "asagus-raw-html"

    llm_provider: str = "disabled"
    llm_model: str = ""
    llm_api_key: str = ""
    llm_base_url: str = ""
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    azure_openai_api_key: str = ""
    azure_openai_endpoint: str = ""
    google_api_key: str = ""
    mistral_api_key: str = ""
    groq_api_key: str = ""
    together_api_key: str = ""
    openrouter_api_key: str = ""
    nvidia_api_key: str = ""
    deepinfra_api_key: str = ""
    cerebras_api_key: str = ""
    fireworks_api_key: str = ""
    huggingface_api_key: str = ""
    perplexity_api_key: str = ""

    brightdata_username: str = ""
    brightdata_password: str = ""
    webshare_api_key: str = ""
    iproyal_api_key: str = ""
    google_geocoding_api_key: str = ""

    crawl_concurrency_limit: int = Field(default=200, ge=1, le=1000)
    discovery_concurrency_limit: int = Field(default=20, ge=1, le=200)
    cpu_worker_processes: int = Field(default=4, ge=1, le=128)
    pipeline_queue_maxsize: int = Field(default=5000, ge=100, le=100000)
    browser_pool_size: int = Field(default=10, ge=0, le=50)
    llm_fallback_cache_days: int = Field(default=7, ge=1, le=30)
    mdp_cold_start_phase: str = "A"
    policy_engine_log_level: str = "INFO"
    robots_cache_ttl_hours: int = Field(default=24, ge=1, le=168)
    domain_token_bucket_capacity: int = Field(default=8, ge=1, le=100)
    domain_token_refill_per_second: float = Field(default=0.25, ge=0.01, le=10)
    selector_fingerprint_min_confidence: float = Field(default=0.75, ge=0.0, le=1.0)
    llm_extraction_min_confidence: float = Field(default=0.50, ge=0.0, le=1.0)

    default_unknown_domain_delay_seconds: float = 2.0
    max_job_limit: int = 5000
    enable_network_fetch: bool = False
    enable_search_discovery: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
