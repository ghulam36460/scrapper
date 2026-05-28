from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, HttpUrl, SecretStr, field_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class LayerName(str, Enum):
    policy = "policy"
    crawl_control = "crawl_control"
    compliance = "compliance"
    fetch = "fetch"
    extraction = "extraction"
    enrichment = "enrichment"
    storage = "storage"
    indexing = "indexing"
    retrieval = "retrieval"
    ai_app = "ai_app"


class JobStatus(str, Enum):
    draft = "draft"
    queued = "queued"
    running = "running"
    paused = "paused"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class FetchMode(str, Enum):
    static = "static"
    dynamic = "dynamic"
    hybrid = "hybrid"


class ExtractionMethod(str, Enum):
    css = "css"
    xpath = "xpath"
    dom_fingerprint = "dom_fingerprint"
    structural_heuristic = "structural_heuristic"
    heuristic = "heuristic"
    llm = "llm"
    manual_review = "manual_review"


class LLMProvider(str, Enum):
    disabled = "disabled"
    anthropic = "anthropic"
    openai = "openai"
    azure_openai = "azure_openai"
    google = "google"
    mistral = "mistral"
    groq = "groq"
    together = "together"
    openrouter = "openrouter"
    nvidia = "nvidia"
    deepinfra = "deepinfra"
    cerebras = "cerebras"
    fireworks = "fireworks"
    huggingface = "huggingface"
    perplexity = "perplexity"
    openai_compatible = "openai_compatible"
    ollama = "ollama"
    custom_http = "custom_http"


class URLType(str, Enum):
    maps_listing_url = "maps_listing_url"
    maps_search_grid = "maps_search_grid"
    website_contact = "website_contact"
    website_about = "website_about"
    website_homepage = "website_homepage"
    website_blog_post = "website_blog_post"
    website_product = "website_product"
    directory_profile = "directory_profile"
    social_profile = "social_profile"
    asset = "asset"
    unknown = "unknown"


class FrontierTier(str, Enum):
    critical = "CRITICAL"
    high = "HIGH"
    medium = "MEDIUM"
    low = "LOW"
    deferred = "DEFERRED"
    blocked = "BLOCKED"


class MDPAction(str, Enum):
    crawl_now = "CRAWL_NOW"
    defer_1h = "DEFER_1H"
    defer_24h = "DEFER_24H"
    skip = "SKIP"
    prioritize_up = "PRIORITIZE_UP"
    prioritize_down = "PRIORITIZE_DOWN"


class MDPPhase(str, Enum):
    heuristic_a = "A_HEURISTIC_0_200"
    hybrid_b = "B_HYBRID_200_1000"
    learned_c = "C_MDP_1000_PLUS"


class ProxyTier(str, Enum):
    residential = "residential"
    isp_static = "isp_static"
    datacenter = "datacenter"
    budget_residential = "budget_residential"


class RelationshipType(str, Enum):
    competitor = "COMPETITOR"
    same_area = "SAME_AREA"
    same_network = "SAME_NETWORK"
    supplies_to = "SUPPLIES_TO"
    partners_with = "PARTNERS_WITH"
    duplicate_of = "DUPLICATE_OF"
    mentions = "MENTIONS"
    links_to = "LINKS_TO"


class SearchEngine(str, Enum):
    duckduckgo = "duckduckgo"
    bing = "bing"
    brave = "brave"
    google = "google"
    startpage = "startpage"
    wikipedia = "wikipedia"
    yandex = "yandex"
    yahoo = "yahoo"
    mojeek = "mojeek"


class SearchAlgorithm(str, Enum):
    inverted_index = "inverted_index"
    tfidf = "tfidf"
    vector_embeddings = "vector_embeddings"
    ann_search = "ann_search"
    bm25 = "bm25"
    learning_to_rank = "learning_to_rank"
    hybrid_retrieval = "hybrid_retrieval"
    dense_bi_encoder = "dense_bi_encoder"
    dense_hnsw = "dense_hnsw"
    cross_encoder = "cross_encoder"
    bert = "bert"
    transformer_attention = "transformer_attention"
    rag = "rag"
    rlhf = "rlhf"
    contrastive_learning = "contrastive_learning"
    self_healing_scraper = "self_healing_scraper"
    react_agent = "react_agent"
    sentiment_analysis = "sentiment_analysis"
    named_entity_recognition = "named_entity_recognition"
    text_summarization = "text_summarization"
    google_dorking = "google_dorking"
    dom_parsing = "dom_parsing"
    css_selector_matching = "css_selector_matching"
    xpath_querying = "xpath_querying"
    safe_api_sessions = "safe_api_sessions"
    headless_browser_automation = "headless_browser_automation"
    graph_network_analysis = "graph_network_analysis"
    computer_vision = "computer_vision"
    predictive_analytics = "predictive_analytics"
    geospatial_intelligence = "geospatial_intelligence"
    universal_web_agent = "universal_web_agent"
    osint_fusion = "osint_fusion"
    learned_sparse_splade = "learned_sparse_splade"
    late_interaction_colbert = "late_interaction_colbert"
    muvera_multi_vector = "muvera_multi_vector"
    rrf_fusion = "rrf_fusion"
    graph_guided = "graph_guided"
    clue_rag_q_iter = "clue_rag_q_iter"
    chain_of_retrieval = "chain_of_retrieval"
    corrective_rag = "corrective_rag"
    causal_feedback = "causal_feedback"
    contextual_bandit = "contextual_bandit"
    cross_encoder_rerank = "cross_encoder_rerank"


class LLMSettings(BaseModel):
    provider: LLMProvider = LLMProvider.disabled
    model: str = ""
    api_key: SecretStr | None = None
    base_url: str | None = None
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    timeout_seconds: int = Field(default=45, ge=5, le=240)
    max_concurrency: int = Field(default=5, ge=1, le=50)
    extra_headers: dict[str, str] = Field(default_factory=dict)

    @field_validator("model")
    @classmethod
    def strip_model(cls, value: str) -> str:
        return value.strip()

    @field_validator("base_url")
    @classmethod
    def strip_base_url(cls, value: str | None) -> str | None:
        return value.strip() if value else None

    def masked(self) -> dict[str, Any]:
        data = self.model_dump(exclude={"api_key"})
        data["has_api_key"] = bool(self.api_key and self.api_key.get_secret_value())
        return data


class ProviderPreset(BaseModel):
    provider: LLMProvider
    label: str
    default_base_url: str = ""
    example_models: list[str] = Field(default_factory=list)
    key_hint: str = ""
    local_only: bool = False
    supports_json_mode: bool = True
    notes: str = ""


class ScrapeStartRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=160)
    location: str = Field(..., min_length=2, max_length=160)
    limit: int = Field(default=100, ge=1, le=5000)
    max_pages: int = Field(default=0, ge=0, le=20000)
    mode: Literal["balanced", "fast", "deep", "research"] = "balanced"
    allowed_domains: list[str] = Field(default_factory=list)
    blocked_domains: list[str] = Field(default_factory=list)
    llm_enabled: bool = True
    archive_raw_html: bool = True
    respect_robots_txt: bool = True
    skip_existing: bool = True
    include_contact_pages: bool = True
    include_social_profiles: bool = True
    require_email: bool = True
    proxy_strategy: Literal["auto", "none", "residential", "isp_static", "datacenter"] = "auto"
    notes: str = ""


class JobEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    job_id: str
    layer: LayerName
    event_type: str
    message: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


class ScrapeJob(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    request: ScrapeStartRequest
    status: JobStatus = JobStatus.queued
    created_at: datetime = Field(default_factory=utc_now)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    total_targets: int = 0
    processed_targets: int = 0
    skipped_targets: int = 0
    duplicate_skips: int = 0
    records_found: int = 0
    llm_calls: int = 0
    browser_renders: int = 0
    current_url: str = ""
    progress_message: str = ""
    error: str = ""


class URLCandidate(BaseModel):
    url: str
    source: str = "seed"
    depth: int = 0
    priority: float = Field(default=0.5, ge=0.0, le=1.0)
    page_type: str = "unknown"
    url_type: URLType = URLType.unknown
    frontier_tier: FrontierTier = FrontierTier.medium
    domain_yield_rate: float = Field(default=0.5, ge=0.0, le=1.0)
    parent_page_yield: float = Field(default=0.5, ge=0.0, le=1.0)
    domain_render_required: bool = False
    domain_ban_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    link_density: float = Field(default=0.0, ge=0.0, le=1.0)
    js_complexity_score: float = Field(default=0.0, ge=0.0, le=1.0)
    last_extraction_confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    time_in_frontier_h: float = Field(default=0.0, ge=0.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SearchDiscoveryRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=300)
    location: str = ""
    engines: list[SearchEngine] = Field(default_factory=lambda: [SearchEngine.duckduckgo])
    max_results: int = Field(default=20, ge=1, le=200)
    region: str = "us-en"
    safesearch: Literal["on", "moderate", "off"] = "moderate"


class SearchDiscoveryResult(BaseModel):
    title: str = ""
    url: str
    snippet: str = ""
    engine: SearchEngine | str = SearchEngine.duckduckgo
    rank: int = 0
    candidate: URLCandidate


class ThroughputProfile(BaseModel):
    io_concurrency: int = Field(default=200, ge=1, le=2000)
    cpu_workers: int = Field(default=4, ge=1, le=128)
    queue_maxsize: int = Field(default=5000, ge=1, le=100000)
    browser_contexts: int = Field(default=10, ge=0, le=100)
    backpressure_policy: Literal["block", "drop_low_priority", "defer_low_priority"] = "defer_low_priority"


class ResearchSearchAlgorithm(BaseModel):
    name: str
    category: SearchAlgorithm
    year: int
    role: str
    implementation_status: Literal["implemented", "adapter_ready", "guarded", "planned"] = "adapter_ready"
    source_url: str = ""
    notes: str = ""


class CapabilityCard(BaseModel):
    key: str
    name: str
    category: Literal["retrieval", "neural", "scraping", "osint", "analytics", "research"]
    status: Literal["implemented", "adapter_ready", "guarded", "planned"] = "implemented"
    safety_boundary: str = ""
    practical_use: str = ""
    source_module: str = ""


class MDPState(BaseModel):
    url_path_depth: int = 0
    url_type: URLType = URLType.unknown
    domain_yield_rate: float = Field(default=0.5, ge=0.0, le=1.0)
    domain_render_required: bool = False
    domain_ban_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    parent_page_yield: float = Field(default=0.5, ge=0.0, le=1.0)
    time_in_frontier_h: float = Field(default=0.0, ge=0.0)
    link_density: float = Field(default=0.0, ge=0.0, le=1.0)
    js_complexity_score: float = Field(default=0.0, ge=0.0, le=1.0)
    last_extraction_conf: float = Field(default=0.5, ge=0.0, le=1.0)


class MDPDecision(BaseModel):
    state: MDPState
    state_key: str = ""
    action: MDPAction
    phase: MDPPhase
    epsilon: float = Field(default=1.0, ge=0.0, le=1.0)
    frontier_tier: FrontierTier = FrontierTier.medium
    expected_yield: float = Field(default=0.0, ge=0.0, le=1.0)
    reward_estimate: float = 0.0
    selected_score: float = 0.0
    q_values: dict[str, float] = Field(default_factory=dict)
    transition_probs: dict[str, float] = Field(default_factory=dict)
    strategy: Literal["maps_bfs", "website_dfs", "priority_queue", "pagerank_recrawl"] = "priority_queue"
    reasons: list[str] = Field(default_factory=list)


class PolicyDecision(BaseModel):
    decision: Literal["crawl", "defer", "skip", "manual_review"] = "crawl"
    fetch_mode: FetchMode = FetchMode.static
    extraction_method: ExtractionMethod = ExtractionMethod.css
    should_index: bool = True
    should_archive: bool = True
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    reasons: list[str] = Field(default_factory=list)
    rules_fired: list[str] = Field(default_factory=list)
    fallback: str = "rule_defaults"
    policy_layer: Literal["rules", "bayesian", "feedback"] = "rules"
    bayesian_score: float = Field(default=0.0, ge=0.0, le=1.0)
    quality_score: float = Field(default=0.0, ge=0.0, le=1.0)
    frontier_tier: FrontierTier = FrontierTier.medium
    mdp_action: MDPAction | None = None
    next_review_seconds: int = 0


class DomainPolicyState(BaseModel):
    domain: str
    pages_seen: int = 0
    rule_hits: int = 0
    bayesian_hits: int = 0
    llm_calls: int = 0
    browser_renders: int = 0
    extraction_confidence_avg: float = Field(default=0.5, ge=0.0, le=1.0)
    domain_yield_rate: float = Field(default=0.5, ge=0.0, le=1.0)
    domain_render_required: bool = False
    domain_ban_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    last_feedback_at: datetime = Field(default_factory=utc_now)


class PolicyFeedback(BaseModel):
    domain: str
    extraction_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    fields_extracted: int = Field(default=0, ge=0)
    render_time_ms: int = Field(default=0, ge=0)
    proxy_cost: float = Field(default=0.0, ge=0.0)
    was_blocked: bool = False
    used_llm: bool = False
    used_browser: bool = False
    created_at: datetime = Field(default_factory=utc_now)


class ComplianceDecision(BaseModel):
    allowed: bool
    delay_seconds: float = Field(default=2.0, ge=0.0)
    reason: str = "default"
    audit_required: bool = True
    robots_cache_hit: bool = False
    crawl_delay_source: Literal["robots", "token_bucket", "job_policy", "default"] = "default"
    gdpr_region: bool = False
    tokens_remaining: float = Field(default=0.0, ge=0.0)


class ProxyEndpoint(BaseModel):
    id: str
    tier: ProxyTier
    provider: str = ""
    endpoint: str = ""
    country_code: str = ""
    active: bool = True
    ban_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    success_rate: float = Field(default=1.0, ge=0.0, le=1.0)
    cooldown_until: datetime | None = None
    last_error: str = ""


class FetchResult(BaseModel):
    url: str
    status_code: int = 0
    final_url: str = ""
    content_type: str = ""
    html: str = ""
    markdown: str = ""
    fetch_mode: FetchMode = FetchMode.static
    render_time_ms: int = 0
    proxy_used: str = ""
    error: str = ""
    fetched_at: datetime = Field(default_factory=utc_now)


class SelectorFingerprint(BaseModel):
    domain: str
    field_name: str
    selector: str
    dom_hash: str
    text_signature: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    created_at: datetime = Field(default_factory=utc_now)
    last_seen_at: datetime = Field(default_factory=utc_now)


class ExtractionStageResult(BaseModel):
    stage: ExtractionMethod
    accepted: bool = False
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    fields_found: list[str] = Field(default_factory=list)
    reason: str = ""


class ExtractedRecord(BaseModel):
    source_url: str
    source: Literal["google_maps", "website_crawl", "directory", "manual"] = "website_crawl"
    name: str = ""
    phone: str = ""
    whatsapp: str = ""
    email: str = ""
    address: str = ""
    city: str = ""
    country_code: str = ""
    website_url: str = ""
    facebook_url: str = ""
    instagram_url: str = ""
    twitter_url: str = ""
    linkedin_url: str = ""
    rating: float | None = None
    review_count: int | None = None
    category: str = ""
    raw_fields: dict[str, Any] = Field(default_factory=dict)
    method: ExtractionMethod = ExtractionMethod.css
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    extraction_trace: list[ExtractionStageResult] = Field(default_factory=list)
    manual_review_required: bool = False


class EnrichedRecord(ExtractedRecord):
    id: str = Field(default_factory=lambda: str(uuid4()))
    email_verified: bool = False
    email_mx_checked: bool = False
    phone_valid: bool = False
    whatsapp_valid: bool = False
    website_alive: bool = False
    lat: float | None = None
    lng: float | None = None
    normalized_area: str = ""
    isic_code: str = ""
    record_completeness: float = Field(default=0.0, ge=0.0, le=1.0)
    duplicate_score: float = Field(default=0.0, ge=0.0, le=1.0)
    dedupe_reasons: list[str] = Field(default_factory=list)
    gdpr_flag: bool = False
    pdpa_flag: bool = False
    entity_tags: list[str] = Field(default_factory=list)
    ner_entities: dict[str, list[str]] = Field(default_factory=dict)
    index_pending: bool = True


class RelationshipCandidate(BaseModel):
    source_record_id: str
    target_record_id: str
    relationship: RelationshipType
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    city: str = ""
    category: str = ""
    has_website: bool | None = None
    has_whatsapp: bool | None = None
    top_k: int = Field(default=20, ge=1, le=100)
    rerank: bool = True


class SearchResult(BaseModel):
    record: EnrichedRecord
    score: float
    source: Literal["bm25", "dense", "rrf", "database"] = "database"
    highlights: list[str] = Field(default_factory=list)


class ObservabilityMetric(BaseModel):
    name: str
    value: float
    unit: str = ""
    status: Literal["ok", "warn", "critical"] = "ok"
    description: str = ""
    labels: dict[str, str] = Field(default_factory=dict)
    updated_at: datetime = Field(default_factory=utc_now)


class SystemHealth(BaseModel):
    status: Literal["ok", "degraded", "down"] = "ok"
    services: dict[str, str] = Field(default_factory=dict)
    checked_at: datetime = Field(default_factory=utc_now)
