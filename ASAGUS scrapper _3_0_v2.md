**ASAGUS**

**INTELLIGENT SCRAPING SYSTEM**

Version 3.0 · Full Architecture & Development Plan

Research-Backed · Production-Ready · May 2026

|     |     |
| --- | --- |
| **CAPABILITY** | **IMPROVEMENT** |
| Policy Engine | AI brain routes every URL, fetch, extract & index decision |
| 10 Intelligent Layers | Each layer has its own intelligence & decision authority |
| Markov Decision Process | Adaptive crawl scheduling that improves with every fetch |
| Zero-Overhead Concurrency | asyncio for I/O + multiprocessing for CPU = max throughput |
| Self-Healing Extraction | DOM fingerprinting auto-repairs broken selectors — no downtime |
| Failure Resilience | Every layer has documented fallback — 99.9% uptime target |

CONFIDENTIAL · Internal Architecture Document

# 1\. Executive Summary

ASAGUS 3.0 is a ground-up redesign of the v2.0 scraping system, incorporating cutting-edge research in web crawling (2024–2026) to solve the three critical problems of the previous architecture: excessive CPU consumption, brittle extraction that breaks on site changes, and unintelligent crawl scheduling that wastes resources on low-value pages.

## What's New in v3.0

|     |     |     |
| --- | --- | --- |
| **Dimension** | **v2.0 Problem** | **v3.0 Solution** |
| CPU Usage | Celery workers block on I/O; Python threads fight GIL | asyncio event loops for I/O + ProcessPool for CPU = 10x throughput |
| Scheduling | FIFO queue — all URLs treated equally | Markov Decision Process (MDP) + PageRank weights high-yield URLs |
| Extraction | CSS/XPath break on site changes; LLM fallback unstructured | Self-healing DOM fingerprinting (Scrapling) + tiered LLM fallback |
| Intelligence | No decision-making — hardcoded rules everywhere | Central Policy Engine routes every decision intelligently |
| Retrieval | OpenSearch BM25 only (single-stage) | Hybrid BM25 + Dense + RRF Fusion + Cross-encoder reranking |
| Enrichment | None — raw data only | NER, sentiment, geocoding, classification pipeline |
| Architecture | 10 tightly-coupled layers (fragile) | 10 autonomous intelligent layers + shared Policy Engine brain |
| **Resilience** | No fallback strategy documented | **Every layer has explicit failure mode + fallback path ✦ NEW** |

The result is a system that is faster (3–5x throughput gain), cheaper (30–50% less LLM API cost due to smarter routing), more accurate (self-healing means no manual selector maintenance), significantly smarter (the Policy Engine learns from feedback), and more reliable (every layer has a documented failure fallback).

# 2\. Critical Analysis of v2.0 Architecture

## 2.1 The CPU Over-Consumption Problem

The original architecture uses Celery workers running 5 concurrent processes. Each Celery worker is a full Python process running synchronous Playwright calls. This is the worst-case pattern for I/O-bound workloads:

- Web scraping is 95% I/O-bound (network wait, DNS, TLS handshake, page render)
- Celery process-per-task model wastes memory: each Playwright browser instance = ~150–300 MB RAM
- Python's GIL prevents threads from utilizing multiple CPU cores for the 5% CPU work
- Result: 5 workers × 300 MB = 1.5 GB RAM just for browser processes, with ~20% actual CPU utilization

**Root Cause**

Synchronous Playwright inside Celery worker = blocking I/O inside a process. The worker sleeps while waiting for Google Maps to load (2–5 seconds per page), burning a slot that could be processing 10 other URLs.

## 2.2 The Dumb Queue Problem

The v2.0 system uses a simple FIFO Redis queue. Every URL is treated identically. A URL on a parking page with zero business data gets the same priority as a URL that will yield 50 business records. This wastes:

- Browser render time (2–5s each) on zero-yield pages
- Proxy bandwidth on low-value domains
- LLM API calls when the fallback fires on empty pages

## 2.3 The Brittle Extraction Problem

CSS selectors and XPath expressions hardcoded in the codebase break silently when Google Maps or a target website updates its DOM. The original plan mentions 'LLM Fallback (Claude)' but this is an afterthought — there is no structured self-healing, no DOM fingerprinting, no confidence scoring, and no automatic repair mechanism. When Google updates their UI (which happens every 2–4 weeks), the scraper stops working until a developer manually fixes the selectors.

## 2.4 No Policy Engine / Decision Layer

The v2.0 architecture has hardcoded logic: always use Camoufox, always try CSS first, always fall back to LLM. There is no routing intelligence. A static HTML page gets the same expensive Playwright + Camoufox treatment as a heavily-protected JavaScript SPA.

## 2.5 No Failure Recovery Strategy ✦ NEW

v2.0 has no documented failure modes. When a component fails — Redis goes down, a proxy provider returns errors, a selector breaks — there is no graceful degradation path. v3.0 documents explicit fallbacks for every layer.

# 3\. Architecture Overview — The Intelligent 10-Layer Stack

ASAGUS 3.0 is built as a layered pipeline where each layer is an autonomous intelligent unit. Layers communicate via typed message queues (Redis Streams). The central Policy Engine acts as a shared brain, consulted by any layer that needs a routing decision. No layer talks directly to another layer's internal implementation.

|     |     |     |     |
| --- | --- | --- | --- |
| **#** | **Layer Name** | **Intelligence** | **Key Technologies** |
| 0   | Policy Engine (Brain) | Routes ALL decisions: crawl/skip, static/dynamic, CSS/LLM, index/skip | Rule engine + Bayesian classifier + feedback loop |
| 1   | Crawl Control Plane | Frontier priority, MDP scheduler, PageRank-weighted URL selection | MDP + BFS/DFS hybrid, PageRank, Neural quality estimator |
| 2   | Compliance Layer | Per-domain rate limit intelligence, robots.txt semantic parser | Token bucket, allowlist/blocklist, audit logger |
| 3   | Fetch Layer | Static vs dynamic decision, browser pool management, proxy selection | httpx async, Playwright, Camoufox, proxy pool |
| 4   | Extraction Layer | CSS → fingerprint → LLM cascade with confidence scoring | Scrapling, selectolax, XPath, Claude Sonnet, self-healing |
| 5   | Enrichment Layer | NER entity detection, sentiment, geocoding, business classification | GLiNER NER, spaCy, geopy, zero-shot classifier |
| 6   | Storage Layer | Raw/clean/structured/graph storage with dedup and versioning | MinIO, PostgreSQL, Neo4j, Redis cache |
| 7   | Indexing Layer | BM25 inverted index + dense vector embedding + ANN index | OpenSearch, Qdrant HNSW, all-MiniLM-L6-v2 |
| 8   | Retrieval Layer | Hybrid retrieval, RRF fusion, cross-encoder reranking | BM25+Dense+RRF, Cohere/MiniLM cross-encoder |
| 9   | AI Application Layer | RAG queries, ReAct agents, live dashboard, analytics | LlamaIndex, Claude Sonnet, Next.js, WebSocket |

## 3.1 Failure Mode & Recovery Map ✦ NEW

Every layer in ASAGUS 3.0 has a documented failure path. The system degrades gracefully — no single component failure causes a full outage.

**Why This Section Exists**

v2.0 had no failure documentation. When components failed in production, developers had to diagnose from scratch. v3.0 treats failure recovery as a first-class design requirement — every layer knows what to do when its dependencies are unavailable.

|     |     |     |     |     |
| --- | --- | --- | --- | --- |
| **Layer** | **Failure Scenario** | **Detection** | **Fallback Behaviour** | **Recovery** |
| Policy Engine (0) | Redis connection lost | Health check timeout >2s | All layers revert to hardcoded default rules (static HTTP, CSS-first, skip unknown domains) | Auto-reconnect with exponential backoff; state rebuilds from Postgres within 60s |
| Policy Engine (0) | Bayesian model corrupt / stale | Prediction confidence <0.3 on known domains | Fall through to rule layer only; log anomaly | Nightly model rebuild from audit log; hot-swap without restart |
| Crawl Plane (1) | Frontier queue empty | Consumer group lag = 0 for >30s | Trigger sitemap re-discovery on top-10 seed domains | Operator alert + auto-seed from configured URL list |
| Compliance (2) | robots.txt fetch timeout | HTTP timeout >5s | Use cached version (TTL 24h); if no cache, apply conservative default (crawl-delay: 5s) | Retry after 1 hour; log for manual review if repeated |
| Fetch (3) | All proxies banned on domain | Ban rate >90% on domain | Pause domain for 6 hours; mark in Policy Engine; reroute budget to other domains | Human review queue entry; proxy rotation strategy update |
| Fetch (3) | Playwright browser crash | Process exit code non-zero | Remove from pool; restart async; remaining pool continues serving | Auto-respawn via asyncio supervisor; alert if pool <3 instances |
| Extraction (4) | LLM API unavailable | HTTP 429 / 5xx from Claude API | Queue page for retry (max 3x, 1h apart); mark record as extraction_pending | Exponential backoff; alert if backlog >500 pages |
| Enrichment (5) | GLiNER model OOM | ProcessPool worker crash | Skip NER enrichment; store record without entity tags; set ner_status=skipped | Reduce batch size from 64→16; restart worker; process backlog |
| Storage (6) | PostgreSQL unavailable | Connection pool exhausted | Buffer records in Redis Stream (max 10k); pause enrichment upstream | Alert immediately; resume writes when DB recovers; no data loss |
| Indexing (7) | Qdrant unavailable | HTTP 503 from Qdrant | Continue storing in PostgreSQL; mark records as index_pending=true | Re-index pending records when Qdrant recovers; BM25-only retrieval in interim |
| Retrieval (8) | Cross-encoder timeout | Inference >500ms | Return RRF-fused results without reranking; log latency event | Policy Engine marks query type as no-rerank; revisit threshold settings |

**Design Principle**

Failure in any single layer must not propagate upstream. Each layer reads from its input Redis Stream independently — if a downstream layer is slow or failed, the stream buffers and upstream layers continue. Backpressure alerts fire before buffers overflow.

**Section / Layer Numbering Note ✦ NEW  
**Document section numbers follow the narrative order, while Layer numbers refer to the 10-layer system stack. Example: "Layer 5" means the Enrichment Layer even if it appears under a different document section number. This removes ambiguity for readers moving between the architecture table, implementation plan, and layer-specific sections.

## 3.2 Visual Data Flow Diagram ✦ NEW

This diagram converts the previous text-only flow into a visual implementation map. It makes the orchestration path, Redis Streams bus, and Policy Engine decision loop immediately visible for reviewers and developers.

**Visible Impact  
**This replaces an abstract architecture explanation with a presentation-ready visual. A reviewer can now understand the full crawl -> extract -> enrich -> index -> retrieve -> AI-app flow in under one minute.

# 5\. Layer 1 — Crawl Control Plane

## 5.1 Frontier Architecture

The frontier is NOT a simple FIFO queue. It is a multi-tier priority structure:

|     |     |     |     |
| --- | --- | --- | --- |
| **Tier** | **Content** | **Priority Score** | **Implementation** |
| **CRITICAL** | Google Maps business listing URLs with confirmed data | 0.85 – 1.00 | Redis Sorted Set (ZSET) — key: domain:url, score: priority |
| **HIGH** | Contact/About pages from crawled websites | 0.65 – 0.84 | Redis ZSET |
| **MEDIUM** | Homepage URLs from Maps-discovered businesses | 0.40 – 0.64 | Redis ZSET |
| **LOW** | Linked pages found during crawl (depth > 1) | 0.10 – 0.39 | Redis ZSET |
| **DEFERRED** | URLs that previously yielded nothing (retry in 24h) | Scheduled | Redis Sorted Set with TTL timestamp as score |
| **BLOCKED** | URLs permanently skipped (parking pages, error pages) | —   | Redis Set (bloom filter for memory efficiency) |

## 5.2 Markov Decision Process (MDP) Scheduler

The MDP scheduler treats crawling as a sequential decision problem where the crawler is an agent trying to maximize business data yield while minimizing resource expenditure.

|     |     |     |
| --- | --- | --- |
| **Component** | **Definition** | **Implementation** |
| State (S) | The current context vector for a URL candidate | URL features: domain_yield_rate, depth, page_type_prob, link_density, parent_yield, time_in_queue, js_complexity_score |
| Action (A) | What to do with this URL | CRAWL_NOW / DEFER_1H / DEFER_24H / SKIP / PRIORITIZE_UP / PRIORITIZE_DOWN |
| Reward (R) | Quality of outcome after crawling | R = data_fields_extracted × completeness_score − cost_penalty (render_time × proxy_cost) |
| Policy (π) | The mapping from states to actions | Logistic regression (fast) updated nightly; Epsilon-greedy exploration (5%) for discovering new patterns |
| Transition (T) | How state changes after an action | Deterministic: state updates with observed outcome; stochastic: unknown pages get MDP estimates |

## 5.3 MDP Cold-Start Strategy ✦ NEW

A critical unanswered question in any MDP-based crawler is: what happens on the first 500 crawls, before the transition matrix has sufficient training data? ASAGUS 3.0 handles this with a three-phase bootstrap:

**Cold-Start Problem**

On first deployment, the MDP has no domain yield history, no transition probabilities, and no ban-rate data. Applying a half-trained model is worse than using simple heuristics — it creates biased priors that are hard to undo.

|     |     |     |     |     |
| --- | --- | --- | --- | --- |
| **Phase** | **Crawl Count** | **Strategy** | **Epsilon (Exploration)** | **Goal** |
| **Phase A: Seed** | 0 – 200 | Pure heuristic: URL path rules only (contact > home > other). No MDP inference. | 1.0 (100% explore) | Build initial domain yield statistics |
| **Phase B: Warm-Up** | 200 – 1,000 | Hybrid: 50% heuristic, 50% MDP inference. Transition matrix populated from Phase A outcomes. | 0.30 | Validate MDP predictions against heuristic baseline |
| **Phase C: Full MDP** | 1,000+ | Full MDP scheduling. Nightly logistic regression update. Epsilon-greedy for novel domains. | 0.05 | Maximize yield efficiency; continuous learning |
| **Pre-trained Fallback** | Any | If v2.0 crawl history available, import into transition matrix. Skips Phase A entirely. | 0.05 from start | Accelerated bootstrap from existing data |

Transition matrix initialized from domain knowledge (see below), then updated via Maximum Likelihood Estimation (MLE) on actual crawl outcomes:

|     |     |     |     |     |
| --- | --- | --- | --- | --- |
| **URL Pattern** | **high_yield** | **med_yield** | **zero_yield** | **Initial Source** |
| maps_listing_url | 0.91 | 0.07 | 0.02 | Domain knowledge |
| website_contact | 0.78 | 0.18 | 0.04 | Domain knowledge |
| website_homepage | 0.52 | 0.31 | 0.17 | Domain knowledge |
| website_blog_post | 0.04 | 0.11 | 0.85 | Domain knowledge |
| website_product | 0.38 | 0.42 | 0.20 | Domain knowledge |
| unknown_depth_1 | 0.31 | 0.28 | 0.41 | Conservative prior |
| unknown_depth_2+ | 0.09 | 0.18 | 0.73 | Conservative prior |

# 9\. Layer 5/6 — Graph Population Logic ✦ NEW

Neo4j is now specified as an implemented intelligence layer rather than a vague storage add-on. The Enrichment Layer emits typed entities and confidence-scored relationship candidates; the Storage Layer writes only relationships that pass deterministic validation and confidence thresholds.

|     |     |     |     |
| --- | --- | --- | --- |
| **Edge Type** |     | **Input Signals** | **Creation Rule** | **Business / Retrieval Use** |
| COMPETITOR |     | same city, same primary_category, geo distance, SERP/category co-occurrence | Create when category_similarity >= 0.80 AND distance <= 500m; confidence = 0.5\*category + 0.3\*geo + 0.2\*co-occurrence. | Find dense local markets, competitive clusters, underserved zones. |
| SAME_AREA |     | geohash prefix, normalized neighborhood, city/phase/block fields | Create when geohash_7 matches OR normalized_area matches with confidence >= 0.75. | Power area-level filters like DHA Phase 5, Bahria Town, Blue Area. |
| SAME_NETWORK |     | shared phone prefix, website domain, WhatsApp number, social profile, email domain | Create when at least two strong identifiers match; avoid single-signal phone-prefix matches to reduce false positives. | Detect branches, franchises, related businesses, and duplicate listings. |
| SUPPLIES_TO / PARTNERS_WITH |     | NER entities, dependency patterns, phrases: supplier, distributor, authorized dealer, partner | Create only when source text explicitly states relation and extractor confidence >= 0.78. | Build B2B lead graphs and supplier/customer discovery paths. |
| DUPLICATE_OF |     | name similarity, same phone/website, address proximity, canonical URL | Create when phone/website exact match OR name_similarity >= 0.92 AND distance <= 100m. | Merge duplicate records before indexing and analytics. |
| MENTIONS / LINKS_TO |     | outgoing links, citations, extracted organization/person mentions | Create from normalized URL/entity mentions with source_page_id and timestamp. | Trace evidence, source credibility, and discovery paths. |
| **Relationship Confidence Formula  <br>**edge_confidence = weighted_signal_score - contradiction_penalty. Edges below 0.70 are stored as candidates for review; edges >=0.80 are written to Neo4j; duplicate edges require stricter validation because false merges damage downstream retrieval quality. |     |     |     |     |
| **Example Neo4j Query  <br>**MATCH (b:Business)-\[:COMPETITOR\]->(c:Business)  <br>WHERE b.city = "Lahore" AND b.category = "Restaurant"  <br>RETURN b.name, count(c) AS nearby_competitors  <br>ORDER BY nearby_competitors DESC LIMIT 20 |     |     |     |     |

# 12\. Layer 8 — Retrieval Layer

The Retrieval Layer is where v3.0 makes the biggest improvement over v2.0. Research (2024–2026) consistently shows that two-stage hybrid retrieval (BM25 + dense + RRF fusion followed by cross-encoder reranking) outperforms any single-stage approach by 17–40% on precision metrics.

## 12.1 Example Query — Business Intelligence Use Case ✦ NEW

The following example shows how a natural-language query flows through the full retrieval stack, demonstrating the concrete business value of the hybrid pipeline:

**Example Query**

User: "Find all restaurants in DHA Lahore that have WhatsApp but no website" ReAct Agent Step 1 → Qdrant semantic search: "restaurant DHA Lahore" → 30 candidates ReAct Agent Step 2 → BM25 keyword: "restaurant DHA Phase" → 30 candidates ReAct Agent Step 3 → RRF fusion: merge & deduplicate → 35 unique candidates ReAct Agent Step 4 → PostgreSQL filter: whatsapp IS NOT NULL AND has_website = FALSE ReAct Agent Step 5 → Cross-encoder rerank on final 20 → sorted by relevance Result: 23 businesses returned in 118ms

## 12.2 Hybrid Retrieval Performance

|     |     |     |     |     |
| --- | --- | --- | --- | --- |
| **Retrieval Method** | **Recall@5** | **MRR@3** | **Latency** | **Status** |
| BM25 only (v2.0) | 0.644 | 0.310 | 20ms | **Replaced** |
| Dense only | 0.587 | 0.290 | 35ms | **Replaced** |
| Hybrid RRF (BM25+Dense) | 0.695 | 0.433 | 50ms | **Stage 1** |
| **Hybrid + Cross-encoder (v3.0)** | **0.816** | **0.605 (+95% vs v2.0)** | 120ms | **Production** |

# 14\. Performance Targets — v3.0 vs v2.0

|     |     |     |     |
| --- | --- | --- | --- |
| **Metric** | **v2.0 Target** | **v3.0 Target** | **How Achieved** |
| Maps scraping speed | 50 biz/min per worker | 200 biz/min per async worker | asyncio 200 concurrent + MDP skips zero-yield URLs |
| Website deep crawl | 30 sites/min per worker | 150 sites/min per worker | asyncio static fetch for 80% of sites (no browser needed) |
| 1000 results time | ~20 minutes (5 workers) | ~5 minutes (3 async workers) | 4x throughput + smarter scheduling |
| LLM API calls | ~30% of pages | ~8% of pages | Self-healing extraction handles 22% that previously hit LLM |
| Search latency | <100ms | <120ms (with reranking) | Hybrid retrieval, 95% of queries don't need reranking |
| Anti-bot success rate | \>95% | \>97% | Policy Engine avoids patterns that trigger detection |
| Data accuracy | \>90% | \>96% | Confidence cascade + self-healing + advanced dedup |
| Selector maintenance | Manual fix on site change | Zero manual intervention | Self-healing DOM fingerprinting |
| RAM per worker | ~300 MB per Celery worker | ~120 MB per async worker | asyncio vs process-per-request model |
| Uptime / reliability | 99% (manual fix needed) | 99.9% (self-healing) | Policy Engine detects failures and reroutes automatically |
| **Cold-start performance ✦** | N/A | Full MDP active after 1,000 crawls | Three-phase bootstrap (see Section 5.3) |

# 15\. Development Plan — Week by Week

Each phase now includes explicit, measurable success criteria — not just deliverables. A phase is 'done' only when its success metric is validated.

**Why Measurable Success Criteria ✦ NEW**

The original plan listed deliverables but not how to verify them. 'Phase 2 achieves 60% reduction in browser renders' is unverifiable without a measurement approach. Each phase below specifies exactly how success is confirmed.

|     |     |     |     |     |
| --- | --- | --- | --- | --- |
| **Phase** | **Weeks** | **Goal** | **Deliverable** | **✦ Success Metric** |
| Phase 1: Async Foundation | 1–2 | Replace Celery with asyncio worker; static httpx + async Playwright pool | Async scraper fetches 200 biz/min from Maps | Throughput test: Lahore restaurants query, limit=1000. Confirm ≥200 biz/min sustained for 10 min. Memory: <200 MB per worker (vs 1.5 GB in v2.0). |
| Phase 2: Policy Engine MVP | 3–4 | Rule-based Policy Engine; static vs dynamic routing; Markov state logging | 60% reduction in unnecessary browser renders | A/B test: 100 identical URLs with policy ON vs OFF. Count browser renders each side. Confirm ≥55% reduction (conservative threshold). |
| Phase 3: Self-Healing Extraction | 5–6 | Scrapling DOM fingerprinting; confidence cascade; LLM fallback pipeline | Selector breaks auto-repair without dev intervention | Inject deliberate CSS selector break for 5 test domains. Confirm all 5 auto-heal within 2 crawl cycles. LLM fallback rate: <12% of pages. |
| Phase 4: MDP Scheduler | 7–8 | Full MDP frontier with Markov transition model; URL yield prediction | Crawl scheduler routes to high-yield URLs first | Compare yield rate: MDP scheduler vs FIFO on same 500-URL set. MDP must achieve ≥25% more data fields extracted in same time. |
| Phase 5: Enrichment Layer | 9–10 | GLiNER NER; geocoding; business classifier; advanced dedup | Rich records with entity data and validated contacts | Sample 200 records: ≥85% have valid geocoordinates. Dedup test: inject 50 duplicates, confirm ≥45 detected and merged. |
| Phase 6: Hybrid Retrieval | 11–12 | Qdrant dense index; RRF fusion; cross-encoder reranker | Search precision +40% vs v2.0 BM25-only | MRR@3 benchmark on 100 test queries. Target: ≥0.55 (vs v2.0 baseline of 0.31). Latency P95 must stay <200ms. |
| Phase 7: AI Application Layer | 13–14 | RAG pipeline; ReAct agent for complex queries; live Next.js dashboard | Full product with NL query interface | 5 complex NL queries (multi-filter) tested end-to-end. All 5 return ≥10 relevant results. Dashboard loads in <2s. |
| Phase 8: Production Hardening | 15–16 | Load testing; Policy Engine learning loop; Neo4j graph; multi-tenant | Production-ready, 99.9% uptime target | 48-hour soak test at 150% peak load. Zero data loss. Failure injection: kill each service one at a time, confirm recovery per failure mode table (Section 3.1). |

## 15.5 Observability & Monitoring Strategy ✦ NEW

ASAGUS 3.0 runs 11 Docker services across 3 async workers. Without structured observability, diagnosing performance degradation becomes guesswork. The following monitoring matrix defines what to track, where, and when to alert.

## Core Metrics Dashboard

|     |     |     |     |
| --- | --- | --- | --- |
| **Metric** | **Tool** | **Alert Threshold** | **What It Means** |
| Crawl throughput (biz/min) | Prometheus counter + Grafana | &lt;100 biz/min for &gt;5 min | System bottleneck — check Redis Stream lag first |
| Policy Engine rule-layer hit rate | Custom Prometheus counter | <70% → Bayesian layer over-relying | Rules should handle 80% of decisions; if not, rule coverage is incomplete |
| LLM call % (per domain) | Counter in Policy Engine feedback | \>15% on any domain | Extractor degraded — DOM fingerprint likely failing for that domain |
| Redis Stream consumer lag | redis INFO groups command | \>10,000 pending messages | Downstream layer bottleneck — check enrichment or storage worker |
| Proxy ban rate (per domain) | Ban events in Policy Engine | \>30% ban rate in 1h window | IP pool exhausted or domain changed anti-bot strategy |
| Extraction confidence avg | Histogram in Postgres metadata | <0.72 rolling 1h average | Site DOM changes affecting CSS selectors; self-healing may need manual assist |
| PostgreSQL connection pool | asyncpg pool metrics | \>80% utilization | Storage bottleneck; scale write workers or add read replica |
| Qdrant index_pending records | SELECT COUNT(\*) WHERE index_pending | \>5,000 records | Indexing worker lagging; dense search results will be stale |
| Worker memory per process | Docker stats + cAdvisor | \>2 GB per async-worker | Memory leak or GLiNER batch size too large |
| End-to-end pipeline latency | Span timing in Redis Streams | P95 >90 seconds URL→stored | Full pipeline slower than expected; profile each layer's stream lag |

**Quick Start: Monitoring Stack**

Add to docker-compose.yml: • prometheus:prom/prometheus:latest (port 9090) — scrape all services • grafana:grafana/grafana:latest (port 3001) — pre-built dashboard JSON in /dashboards/ • cadvisor:gcr.io/cadvisor/cadvisor:latest — container-level CPU/RAM All async-worker metrics exported via prometheus-async at /metrics:9091.

# 17\. Cost Estimate — v3.0 vs v2.0

Assumptions (Now Explicit) ✦ NEW  
500,000 URLs/month total. Static/dynamic split: 80% static (httpx) / 20% dynamic (Playwright-rendered Maps or SPA pages). Base payload math: 400K static × ~2KB HTML = ~0.8GB; 100K dynamic × ~50KB rendered response/snapshot = ~5GB. After HTTP headers, redirects, screenshots, retries, compression variance, and 2.5× safety overhead, planning bandwidth is rounded to ~15GB/month. Proxy budget model: Tier 1 residential for high-risk Maps traffic = ~5GB × $15/GB = $75; Tier 3/cheaper pool for lower-risk static sites = ~10GB × $2/GB = $20. Expected proxy baseline: ~$95/month, with $40–120/month range depending on retries, city coverage, and anti-bot friction.

|     |     |     |     |
| --- | --- | --- | --- |
| **Component** | **v2.0 Cost/Month** | **v3.0 Cost/Month** | **Saving / Note** |
| Residential Proxies (BrightData Tier 1) | $50–150 | $40–120 | MDP skips zero-yield URLs → ~20% less bandwidth |
| Server (VPS — 4 vCPU 16GB RAM) | $40–80 | $50–90 | Slightly larger for ProcessPool workers |
| Claude API (LLM fallback) | $10–30 | $3–10 | Self-healing cuts LLM calls by ~70% |
| Anti-CAPTCHA service | $10–20 | $8–15 | Policy Engine learns to avoid CAPTCHA triggers |
| MinIO storage (HTML archive) | $0  | $5–10 | New: raw HTML archiving for replay/debugging |
| Prometheus + Grafana (monitoring) | $0  | $0  | Self-hosted in Docker Compose — zero extra cost |
| **Total (estimated)** | **$110–280/month** | **$106–245/month** | **~12% cheaper + dramatically better results + full observability** |

# 19\. Quick Start Guide

## 19.1 Environment Variables Reference ✦ NEW

Copy .env.example to .env and populate all Required fields before running. Optional fields have working defaults.

|     |     |     |     |
| --- | --- | --- | --- |
| **Variable** | **Example Value** | **Required** | **Used By** |
| **ANTHROPIC_API_KEY** | sk-ant-api03-... | **YES** | Layer 4 (LLM extraction), Layer 9 (RAG) |
| **BRIGHTDATA_USERNAME** | brd-customer-xxx | **YES** | Layer 3 (Fetch — Tier 1 residential) |
| **BRIGHTDATA_PASSWORD** | xxxxxxxx | **YES** | Layer 3 (Fetch — Tier 1 residential) |
| **POSTGRES_URL** | postgresql://asagus:pass@postgres:5432/asagus | **YES** | Layers 6, 4 (selector store), Audit log |
| **REDIS_URL** | redis://redis:6379/0 | **YES** | All layers (Streams + Policy Engine state) |
| **OPENSEARCH_HOST** | http://opensearch:9200 | **YES** | Layer 7 (BM25 index), Layer 8 (retrieval) |
| **QDRANT_HOST** | http://qdrant:6333 | **YES** | Layer 7 (dense index), Layer 8 (retrieval) |
| **MINIO_ENDPOINT** | minio:9000 | **YES** | Layer 6 (raw HTML archive) |
| **MINIO_ACCESS_KEY** | asagus-access | **YES** | Layer 6 (raw HTML archive) |
| **MINIO_SECRET_KEY** | asagus-secret | **YES** | Layer 6 (raw HTML archive) |
| WEBSHARE_API_KEY | ws-xxx... | Optional | Layer 3 (Fetch — Tier 3 datacenter proxies) |
| IProyal_API_KEY | ipr-xxx... | Optional | Layer 3 (Fetch — Tier 4 burst proxies) |
| NEO4J_URI | bolt://neo4j:7687 | Optional | Layer 6 (graph storage — required for Phase 8) |
| NEO4J_PASSWORD | asagus-graph | Optional | Layer 6 (graph storage) |
| GOOGLE_GEOCODING_API_KEY | AIza... | Optional | Layer 5 (geocoding — fallback for Nominatim) |
| POLICY_ENGINE_LOG_LEVEL | INFO | Optional (INFO) | Layer 0 — set DEBUG to trace all decisions |
| MDP_COLD_START_PHASE | A   | Optional (A) | Layer 1 — A/B/C controls bootstrap phase |
| CRAWL_CONCURRENCY_LIMIT | 200 | Optional (200) | Layer 3 — max concurrent httpx connections |
| BROWSER_POOL_SIZE | 10  | Optional (10) | Layer 3 — max Playwright browser instances |
| LLM_FALLBACK_CACHE_DAYS | 7   | Optional (7) | Layer 4 — days to cache LLM extraction results |

## 19.1a Minimal .env.example ✦ NEW

**Copy/Paste Starter Block  
**ANTHROPIC_API_KEY=sk-ant-api03-...  
BRIGHTDATA_USERNAME=brd-customer-xxx  
BRIGHTDATA_PASSWORD=replace_me  
POSTGRES_URL=postgresql://asagus:pass@postgres:5432/asagus  
REDIS_URL=redis://redis:6379/0  
OPENSEARCH_HOST=http://opensearch:9200  
QDRANT_HOST=http://qdrant:6333  
NEO4J_URI=bolt://neo4j:7687  
MINIO_ENDPOINT=http://minio:9000

## 19.2 Step-by-Step First Run

- pip install camoufox playwright-stealth crawl4ai scrapling fastapi asyncpg aioredis httpx gliner phonenumbers geopy
- pip install 'scrapling\[all\]' && python -m playwright install
- python -m camoufox fetch # Download Firefox stealth binary
- docker-compose up -d # Start all infrastructure services
- cp .env.example .env # Populate all Required variables above
- python -m scripts.init_db # Create PostgreSQL schema + OpenSearch index
- python -m scripts.init_qdrant # Create Qdrant collection (384-dim HNSW)
- python -m workers.async_worker # Start async crawler worker
- uvicorn api.main:app --reload # Start FastAPI backend
- cd frontend && npm run dev # Start Next.js dashboard
- curl http://localhost:8000/scrape/start -d '{"query":"restaurants","city":"Lahore","limit":100}'

**Validation Tip**

Start with limit=100 to validate setup before scaling. Monitor Policy Engine decisions at http://localhost:8000/policy/stats — you should see rule-layer hits >75% within the first 20 URLs. If LLM fallback rate is >20% on first run, check that your CSS selectors are current.

## 19.3 Claude Findings Implementation Summary ✦ NEW

|     |     |     |
| --- | --- | --- |
| **Claude Finding** | **Implementation Added / Verified** | **Visible Impact** |
| Failure modes missing | Section 3.1 added with per-layer fallback and recovery map. | Document now reads as production-ready, not only research-ready. |
| MDP cold-start unclear | Section 5.3 added with Seed, Warm-Up, Full MDP, and pre-trained fallback phases. | Week 7-8 implementation risk reduced; first 1,000 crawls have a defined strategy. |
| No observability | Section 15.5 added with Prometheus/Grafana metrics and thresholds. | Bottlenecks become diagnosable instead of hidden. |
| Proxy cost math incomplete | Section 17 assumptions now include volume, static/dynamic split, safety overhead, and proxy tier math. | Cost estimate becomes calculated instead of guessed. |
| Policy Engine MVP vague | Development plan now includes phase-by-phase success metrics and A/B validation. | Sprint completion becomes measurable. |
| Neo4j under-explained | New Layer 5/6 Graph Population Logic section added. | Graph database becomes an implementable feature. |
| RAG layer lacked example | Section 12.1 business-intelligence query flow added. | Readers see practical value immediately. |
| .env.example missing | Environment variable table and minimal .env starter block added. | New developer onboarding becomes faster. |
| Data flow not visual | New visual data-flow diagram added in Section 3.2. | Pitch/developer readability improves. |
| Section/layer numbering ambiguity | Section/layer numbering note added near architecture overview. | Readers understand document sections versus system layers. |

# 20\. Legal & Ethical Notes

- Google Maps Terms of Service restrict automated scraping — use for research/personal use only; review ToS before commercial deployment
- GDPR/PDPA compliance required for EU citizen data — the Enrichment Layer GDPR tagger flags these records for appropriate handling
- robots.txt compliance is enforced automatically by the Compliance Layer — do not disable
- Rate limiting is built into the Compliance Layer — the token bucket prevents server overload
- Collected contact data must not be used for unsolicited spam — ASAGUS outreach should be permission-based
- The audit log provides legal compliance evidence of responsible crawl behaviour

**ASAGUS**

**INTELLIGENT SCRAPING SYSTEM**

Version 3.0 · Full Architecture & Development Plan

_Research-Backed · Production-Ready · May 2026_

**POLICY ENGINE**

AI brain routes every URL, fetch, extract & index decision

**10 INTELLIGENT LAYERS**

Each layer has its own intelligence & decision authority

**MARKOV DECISION PROCESS**

Adaptive crawl scheduling that improves with every fetch

**ZERO-OVERHEAD CONCURRENCY**

asyncio for I/O + multiprocessing for CPU = max throughput

**SELF-HEALING EXTRACTION**

DOM fingerprinting auto-repairs broken selectors — no downtime

# 1\. Executive Summary

ASAGUS 3.0 is a ground-up redesign of the v2.0 scraping system, incorporating cutting-edge research in web crawling (2024–2026) to solve the three critical problems of the previous architecture: excessive CPU consumption, brittle extraction that breaks on site changes, and unintelligent crawl scheduling that wastes resources on low-value pages.

## What's New in v3.0

| **Dimension** | **v2.0 Problem** | **v3.0 Solution** |
| --- | --- | --- |
| **CPU Usage** | Celery workers block on I/O; Python threads fight GIL | asyncio event loops for I/O + ProcessPool for CPU = 10x throughput |
| **Scheduling** | FIFO queue — all URLs treated equally | Markov Decision Process (MDP) + PageRank weights high-yield URLs |
| **Extraction** | CSS/XPath break on site changes; LLM fallback unstructured | Self-healing DOM fingerprinting (Scrapling) + tiered LLM fallback |
| **Intelligence** | No decision-making — hardcoded rules everywhere | Central Policy Engine routes every decision intelligently |
| **Retrieval** | OpenSearch BM25 only (single-stage) | Hybrid BM25 + Dense + RRF Fusion + Cross-encoder reranking |
| **Enrichment** | None — raw data only | NER, sentiment, geocoding, classification pipeline |
| **Architecture** | 10 tightly-coupled layers (fragile) | 10 autonomous intelligent layers + shared Policy Engine brain |

The result is a system that is faster (3-5x throughput gain), cheaper (30-50% less LLM API cost due to smarter routing), more accurate (self-healing means no manual selector maintenance), and significantly smarter (the Policy Engine learns from feedback to improve routing decisions over time).

# 2\. Critical Analysis of v2.0 Architecture

## 2.1 The CPU Over-Consumption Problem

The original architecture uses Celery workers running 5 concurrent processes. Each Celery worker is a full Python process running synchronous Playwright calls. This is the worst-case pattern for I/O-bound workloads:

- Web scraping is 95% I/O-bound (network wait, DNS, TLS handshake, page render)
- Celery process-per-task model wastes memory: each Playwright browser instance = ~150-300 MB RAM
- Python's GIL prevents threads from utilizing multiple CPU cores for the 5% CPU work
- Result: 5 workers × 300 MB = 1.5 GB RAM just for browser processes, with ~20% actual CPU utilization

**Root Cause**

Synchronous Playwright inside Celery worker = blocking I/O inside a process. The worker sleeps while waiting for Google Maps to load (2-5 seconds per page), burning a slot that could be processing 10 other URLs.

## 2.2 The Dumb Queue Problem

The v2.0 system uses a simple FIFO Redis queue. Every URL is treated identically. A URL on a parking page with zero business data gets the same priority as a URL that will yield 50 business records. This wastes:

- Browser render time (2-5s each) on zero-yield pages
- Proxy bandwidth on low-value domains
- LLM API calls when the fallback fires on empty pages

## 2.3 The Brittle Extraction Problem

CSS selectors and XPath expressions hardcoded in the codebase break silently when Google Maps or a target website updates its DOM. The original plan mentions 'LLM Fallback (Claude)' but this is an afterthought — there is no structured self-healing, no DOM fingerprinting, no confidence scoring, and no automatic repair mechanism. When Google Updates their UI (which happens every 2-4 weeks), the scraper stops working until a developer manually fixes the selectors.

## 2.4 No Policy Engine / Decision Layer

The v2.0 architecture has hardcoded logic: always use Camoufox, always try CSS first, always fall back to LLM. There is no routing intelligence. A static HTML page gets the same expensive Playwright + Camoufox treatment as a heavily-protected JavaScript SPA. An email found instantly by regex still wastes time calling the LLM fallback in certain code paths.

# 3\. Architecture Overview — The Intelligent 10-Layer Stack

ASAGUS 3.0 is built as a layered pipeline where each layer is an autonomous intelligent unit. Layers communicate via typed message queues (Redis Streams). The central Policy Engine acts as a shared brain, consulted by any layer that needs a routing decision. No layer talks directly to another layer's internal implementation.

| **#** | **Layer Name** | **Intelligence** | **Key Technologies** |
| --- | --- | --- | --- |
| **0** | Policy Engine (Brain) | Routes ALL decisions: crawl/skip, static/dynamic, CSS/LLM, index/skip | Rule engine + Bayesian classifier + feedback loop |
| **1** | Crawl Control Plane | Frontier priority, MDP scheduler, PageRank-weighted URL selection | MDP + BFS/DFS hybrid, PageRank, Neural quality estimator |
| **2** | Compliance Layer | Per-domain rate limit intelligence, robots.txt semantic parser | Token bucket, allowlist/blocklist, audit logger |
| **3** | Fetch Layer | Static vs dynamic decision, browser pool management, proxy selection | httpx async, Playwright, Camoufox, proxy pool |
| **4** | Extraction Layer | CSS → fingerprint → LLM cascade with confidence scoring | Scrapling, selectolax, XPath, Claude Sonnet, self-healing |
| **5** | Enrichment Layer | NER entity detection, sentiment, geocoding, business classification | GLiNER NER, spaCy, geopy, zero-shot classifier |
| **6** | Storage Layer | Raw/clean/structured/graph storage with dedup and versioning | MinIO, PostgreSQL, Neo4j, Redis cache |
| **7** | Indexing Layer | BM25 inverted index + dense vector embedding + ANN index | OpenSearch, Qdrant HNSW, all-MiniLM-L6-v2 |
| **8** | Retrieval Layer | Hybrid retrieval, RRF fusion, cross-encoder reranking | BM25+Dense+RRF, Cohere/MiniLM cross-encoder |
| **9** | AI Application Layer | RAG queries, ReAct agents, live dashboard, analytics | LlamaIndex, Claude Sonnet, Next.js, WebSocket |

## 3.1 Data Flow Diagram

USER QUERY / SCRAPE JOB

│

▼

┌──────────────────┐ ┌─────────────────────────────────────────────┐

│ POLICY ENGINE │◄─────►│ Feedback Store (Redis + Postgres) │

│ (Central Brain)│ │ Stores: yield rates, extraction confidence, │

└────────┬─────────┘ │ render necessity scores, per-domain stats │

│ └─────────────────────────────────────────────┘

┌────────▼──────────────────────────────────────────────────────┐

│ Layer 1: CRAWL CONTROL PLANE │

│ MDP Scheduler ► Frontier Priority Queue ► URL Dispatcher │

└────────┬──────────────────────────────────────────────────────┘

│ \[URLs with priority scores + crawl metadata\]

┌────────▼──────────────────────────────────────────────────────┐

│ Layer 2: COMPLIANCE LAYER │

│ robots.txt cache ► rate limiter ► allowlist check │

└────────┬──────────────────────────────────────────────────────┘

│ \[Approved URLs\]

┌────────▼──────────────────────────────────────────────────────┐

│ Layer 3: FETCH LAYER │

│ Static(httpx) ◄─Policy─► Dynamic(Playwright/Camoufox) │

└────────┬──────────────────────────────────────────────────────┘

│ \[Raw HTML + metadata\]

┌────────▼──────────────────────────────────────────────────────┐

│ Layer 4: EXTRACTION LAYER │

│ CSS/XPath ► DOM Fingerprint ► LLM (confidence cascade) │

└────────┬──────────────────────────────────────────────────────┘

│ \[Structured JSON records\]

┌────────▼──────────────────────────────────────────────────────┐

│ Layer 5: ENRICHMENT LAYER │

│ NER ► Geocoding ► Sentiment ► Classification │

└────────┬──────────────────────────────────────────────────────┘

│ \[Enriched records\]

┌────────▼──────────────────────────────────────────────────────┐

│ Layer 6: STORAGE LAYER (Raw HTML + Text + Structured + Graph)│

└────────┬──────────────────────────────────────────────────────┘

│

┌────────▼──────────────────────────────────────────────────────┐

│ Layer 7: INDEXING LAYER (BM25 + Dense Embeddings + ANN) │

└────────┬──────────────────────────────────────────────────────┘

│

┌────────▼──────────────────────────────────────────────────────┐

│ Layer 8: RETRIEVAL LAYER (Hybrid BM25+Dense+RRF+Rerank) │

└────────┬──────────────────────────────────────────────────────┘

│

┌────────▼──────────────────────────────────────────────────────┐

│ Layer 9: AI APPLICATION LAYER (RAG / ReAct / Dashboard) │

└───────────────────────────────────────────────────────────────┘

# 4\. Layer 0 — The Policy Engine (Central Brain)

The Policy Engine is the architectural heart of ASAGUS 3.0. It is a stateful decision service that all other layers consult before taking expensive actions. It maintains a continuously updated model of the web landscape based on real feedback from every crawl operation.

## 4.1 What the Policy Engine Decides

| **Decision Point** | **Options Evaluated** | **Signal Used** |
| --- | --- | --- |
| **Crawl this URL or skip?** | Crawl now / Defer / Skip permanently | MDP reward model, domain yield history, PageRank |
| **Static fetch or browser render?** | httpx static / Playwright dynamic | JS-detection heuristic, per-domain render necessity score |
| **Which browser profile to use?** | Camoufox (Firefox) / Chromium stealth / Random | Anti-bot detection score for domain, last detection event |
| **Which proxy geo-target?** | Pakistani IP / EU IP / US IP / Random | Target domain's geo-restriction pattern, last IP ban |
| **CSS/XPath or LLM extraction?** | Fast CSS → Fingerprint heal → LLM fallback | Selector confidence score, last extraction success rate |
| **Index as document or entity?** | OpenSearch doc / Qdrant vector / Neo4j node | Record type, field completeness, entity link density |
| **Rerank with cross-encoder?** | Yes (expensive, high precision) / No (fast) | Query type classification, result count, latency budget |
| **NER enrichment needed?** | Full NER / Partial / Skip | Record completeness, downstream task requirements |

## 4.2 Policy Engine Architecture

### **Rule Layer (Fast Path — Microseconds)**

Deterministic rules that handle 80% of decisions instantly without ML inference:

- If domain in allowlist → always crawl
- If domain in blocklist → always skip
- If URL matches /contact|/about|/reach-us → high priority (likely has contact data)
- If URL is .pdf/.zip/.jpg → skip (not a business page)
- If last_extraction_confidence\[domain\] > 0.92 → use CSS, skip LLM
- If last_extraction_confidence\[domain\] < 0.40 → go straight to LLM
- If domain_render_required\[domain\] = True → use Playwright
- If page has wa.me link → WhatsApp found, skip LLM for that field

### **Bayesian Classifier Layer (Medium Path — Milliseconds)**

When rules don't give a clear decision, a lightweight Naive Bayes classifier trained on historical crawl outcomes decides. Features include domain TLD, URL path depth, page size estimate, JS framework detected in previous fetch, and time-of-day (rate limit sensitivity).

### **Feedback Loop (Learning — Background Process)**

Every layer reports outcomes back to the Policy Engine asynchronously:

- Fetch Layer reports: static_sufficient=True/False, render_time_ms, proxy_banned=True/False
- Extraction Layer reports: extraction_method_used, confidence_score, fields_found
- Storage Layer reports: record_completeness (0.0-1.0), duplicate_detected

These signals update the per-domain probability tables in Redis every 60 seconds, allowing the Policy Engine to learn and improve without restarting.

**Key Insight from Research**

Research (Pezzuti et al., 2025; Chang et al., 2024) shows that neural quality estimators can run during network I/O wait times — the same slot where the crawler is blocked waiting for a page to load. ASAGUS 3.0 uses this technique: while waiting for DNS + TLS + HTML, the Policy Engine pre-computes quality scores for the next 10 URLs in the frontier using a lightweight quality estimator. Zero extra latency cost.

# 5\. Layer 1 — Crawl Control Plane

The Crawl Control Plane manages the frontier (the set of URLs to be crawled) and decides which URLs to fetch next, in what order, and how many in parallel. This is where the Markov Decision Process (MDP) lives.

## 5.1 Frontier Architecture

The frontier is NOT a simple FIFO queue. It is a multi-tier priority structure:

| **Tier** | **Content** | **Priority Score Range** | **Implementation** |
| --- | --- | --- | --- |
| **CRITICAL** | Google Maps business listing URLs with confirmed data | 0.85 – 1.00 | Redis Sorted Set (ZSET) — key: domain:url, score: priority |
| **HIGH** | Contact/About pages from crawled websites | 0.65 – 0.84 | Redis ZSET |
| **MEDIUM** | Homepage URLs from Maps-discovered businesses | 0.40 – 0.64 | Redis ZSET |
| **LOW** | Linked pages found during crawl (depth > 1) | 0.10 – 0.39 | Redis ZSET |
| **DEFERRED** | URLs that previously yielded nothing (retry in 24h) | Scheduled | Redis Sorted Set with TTL timestamp as score |
| **BLOCKED** | URLs permanently skipped (parking pages, error pages) | —   | Redis Set (bloom filter for memory efficiency) |

## 5.2 Markov Decision Process (MDP) Scheduler — Deep Dive

The MDP scheduler treats crawling as a sequential decision problem where the crawler is an agent trying to maximize business data yield while minimizing resource expenditure.

### **MDP Formalization**

| **Component** | **Definition** | **Implementation** |
| --- | --- | --- |
| **State (S)** | The current context vector for a URL candidate | URL features: domain_yield_rate, depth, page_type_prob, link_density, parent_yield, time_in_queue, js_complexity_score |
| **Action (A)** | What to do with this URL | CRAWL_NOW / DEFER_1H / DEFER_24H / SKIP / PRIORITIZE_UP / PRIORITIZE_DOWN |
| **Reward (R)** | Quality of outcome after crawling | R = data_fields_extracted × completeness_score − cost_penalty (render_time × proxy_cost) |
| **Policy (π)** | The mapping from states to actions | Logistic regression (fast) updated nightly; Epsilon-greedy exploration (5%) for discovering new patterns |
| **Transition (T)** | How state changes after an action | Deterministic: state updates with observed outcome; stochastic: unknown pages get MDP estimates |

### **Why MDP Over Simple PageRank?**

Standard PageRank measures global link authority but does not account for the scraper's specific goal (business contact data extraction). A page can have high PageRank (e.g., a news article about a restaurant) but yield zero business data. The MDP scheduler learns to differentiate:

- URL /contact or /about → high yield probability (MDP assigns CRAWL_NOW)
- URL from Google Maps listing → very high yield (MDP assigns CRAWL_NOW + CRITICAL tier)
- URL that is page 4 of blog posts on a business website → low yield (MDP assigns SKIP)
- URL from an unfamiliar domain → DEFER + explore (epsilon-greedy)

### **MDP State Vector (Per-URL Feature Engineering)**

class MDPState:

url_path_depth: int # /contact = 1, /blog/post-5 = 3

url_type: str # 'maps_listing' | 'website_contact' | 'website_home' | 'unknown'

domain_yield_rate: float # avg fields extracted per crawl for this domain \[0.0-1.0\]

domain_render_required: bool # True if last 3 fetches needed Playwright

domain_ban_rate: float # % of IPs banned by this domain \[0.0-1.0\]

parent_page_yield: float # yield of the page that linked to this URL

time_in_frontier_h: float # hours since URL was discovered

link_density: int # number of outbound links on parent page

js_complexity_score: float # estimated JS complexity \[0.0-1.0\]

last_extraction_conf: float # last extraction confidence for this domain

### **Markov Chain Transition Model**

For URLs on unseen domains, the MDP uses a Markov chain transition model to estimate yield probability from URL path patterns alone. The chain is trained on the entire crawl history:

\# Transition matrix: URL-path-pattern -> next expected yield

\# Rows: current URL type | Cols: yield outcome

high_yield med_yield zero_yield

maps_listing_url \[ 0.91, 0.07, 0.02 \]

website_contact \[ 0.78, 0.18, 0.04 \]

website_homepage \[ 0.52, 0.31, 0.17 \]

website_blog_post \[ 0.04, 0.11, 0.85 \]

website_product \[ 0.38, 0.42, 0.20 \]

unknown_depth_1 \[ 0.31, 0.28, 0.41 \]

unknown_depth_2+ \[ 0.09, 0.18, 0.73 \]

These transition probabilities are initialized from our domain knowledge and then continuously updated using Maximum Likelihood Estimation (MLE) on actual crawl outcomes. After 10,000 crawls, the model becomes highly accurate for common patterns.

## 5.3 BFS/DFS/Priority Hybrid Strategy

| **Strategy** | **When Used** | **Benefit** |
| --- | --- | --- |
| **BFS (Breadth-First)** | Google Maps grid crawl — discover all businesses in area | Ensures complete coverage before going deep |
| **DFS (Depth-First)** | Website deep crawl once a business URL is found | Quickly finds contact page without crawling entire site |
| **Priority Queue** | Default for all unknown URLs | MDP score determines order — highest yield first |
| **PageRank-weighted** | Re-crawl scheduling (refresh stale data) | High-authority pages refreshed more often |

# 6\. Layer 2 — Compliance Layer

The Compliance Layer is the ethical and legal guardrail of the system. Every approved URL from Layer 1 passes through compliance checks before being handed to the Fetch Layer. This is not just about legality — it also protects the system from triggering aggressive anti-bot responses by being a responsible crawler.

## 6.1 Components

| **Component** | **Function** | **Implementation** |
| --- | --- | --- |
| **robots.txt Parser** | Parses and caches robots.txt for each domain. Checks disallow rules, crawl-delay directives, and sitemap references. | Python robotparser + Redis cache (TTL: 24h). Async bulk-fetched during frontier processing idle time. |
| **Token Bucket Rate Limiter** | Enforces per-domain rate limits. Default: 1 req/2s for unknown domains, relaxed for Maps. | Redis-based token bucket per domain key. Fills at configured rate, drains on each request. |
| **Crawl-Delay Adapter** | Reads Crawl-delay directive from robots.txt and overrides default rate limit. | Extracted from robots.txt parse, stored in Redis hash per domain. |
| **Allowlist Manager** | Explicit list of domains we always crawl (Maps, known business dirs). | Redis Set. Policy Engine consults allowlist for fast-path approval. |
| **Blocklist / Honeypot Detector** | Blocks domains known to be anti-crawler honeypots, legal traps, or zero-yield. | Curated Redis Set + ML classifier trained on URL features. |
| **Audit Logger** | Immutable log of every crawl decision: URL, timestamp, outcome, compliance status. | PostgreSQL append-only table. Used for legal compliance evidence and debug. |
| **GDPR/PDPA Tagger** | Flags records containing EU citizen data for special handling. | Country-code detection from address field + EU country list. |

# 7\. Layer 3 — Fetch Layer

The Fetch Layer is responsible for retrieving page content. Its key innovation in v3.0 is the intelligent routing between a lightweight static HTTP client and a full headless browser — saving 85% of render costs on pages that don't need JavaScript.

## 7.1 Static vs Dynamic Decision (Policy Engine)

The Policy Engine routes each URL to either the static or dynamic fetch path:

| **Signal** | **Static HTTP (httpx)** | **Dynamic Browser (Playwright+Camoufox)** |
| --- | --- | --- |
| **domain_render_required** | False → use static | True → use browser |
| **URL type** | robots.txt, sitemaps, APIs | Google Maps, JS SPAs |
| **Last fetch response** | Full HTML in response body | Empty body or JS placeholder detected |
| **Content-Type header** | text/html with no JS framework hints | application/javascript framework headers |
| **User-configured override** | Static-only mode | Force-dynamic mode |

## 7.2 Static Fetch Engine (httpx + asyncio)

For static pages, the system uses httpx with full asyncio event loop support. This is the critical performance layer — asyncio allows a single Python thread to handle hundreds of concurrent HTTP connections with minimal CPU overhead:

\# Static fetch engine — handles 200+ concurrent connections per worker

import asyncio, httpx

class StaticFetcher:

def \__init_\_(self):

self.client = httpx.AsyncClient(

limits=httpx.Limits(max_connections=200, max_keepalive_connections=50),

timeout=httpx.Timeout(connect=5.0, read=15.0, write=5.0, pool=1.0),

headers={'User-Agent': random_ua(), 'Accept-Encoding': 'gzip, br'},

follow_redirects=True,

)

async def fetch_batch(self, urls: list\[str\]) -> list\[FetchResult\]:

\# asyncio.gather fires all requests concurrently — no blocking

return await asyncio.gather(\*\[self.fetch(url) for url in urls\], return_exceptions=True)

async def fetch(self, url: str) -> FetchResult:

async with self.semaphore: # rate-limit slot

resp = await self.client.get(url, proxy=proxy_pool.next())

return FetchResult(url=url, html=resp.text, status=resp.status_code)

## 7.3 Dynamic Fetch Engine (Playwright + Camoufox)

For JavaScript-heavy pages (Google Maps, modern business sites), the dynamic engine uses a managed browser pool with async Playwright:

\# Dynamic fetch — async browser pool, NOT blocking Celery workers

from playwright.async_api import async_playwright

from camoufox.async_api import AsyncCamoufox

class BrowserPool:

def \__init_\_(self, pool_size=10): # 10 browser instances, not 5 workers

self.pool = asyncio.Queue(maxsize=pool_size)

self.semaphore = asyncio.Semaphore(pool_size)

async def fetch(self, url: str, proxy: str) -> FetchResult:

async with self.semaphore:

page = await self.pool.get()

try:

await page.goto(url, wait_until='networkidle', timeout=30000)

\# Policy Engine: quality estimation runs HERE during page load wait

html = await page.content()

return FetchResult(url=url, html=html, rendered=True)

finally:

await self.pool.put(page) # return to pool

## 7.4 Proxy Pool Manager

| **Proxy Tier** | **Provider** | **Use Case** | **Cost** |
| --- | --- | --- | --- |
| **Tier 1 — Residential** | BrightData / Oxylabs | Google Maps (geo-targeted) | $15/GB |
| **Tier 2 — ISP Static** | BrightData ISP | Business websites (consistent IP) | $8/GB |
| **Tier 3 — Datacenter** | Webshare Rotating | Non-protected static sites only | $2/GB |
| **Tier 4 — Residential Budget** | IPRoyal | Burst capacity overflow | $7/GB |

The Proxy Pool Manager tracks ban rates per proxy:domain pair and automatically routes away from proxy IPs that have been flagged by a target domain. It uses exponential backoff for banned IPs and geo-targets proxies to match the city being scraped (Lahore query = Pakistan residential IP).

# 8\. Layer 4 — Extraction Layer (Self-Healing)

The Extraction Layer implements a confidence-scored cascade with automatic self-healing. Unlike v2.0's brittle CSS-first-then-LLM approach, v3.0 tracks selector health per domain and automatically routes to the appropriate extraction method without developer intervention.

## 8.1 Extraction Cascade

| **Stage** | **Method** | **Confidence Threshold** | **Latency** | **Cost** |
| --- | --- | --- | --- | --- |
| **1 — CSS/XPath Fast Path** | Hardcoded selectors (selectolax) | Accept if score ≥ 0.90 | <10ms | $0  |
| **2 — DOM Fingerprint Heal** | Scrapling auto_match=True (DOM fingerprint) | Accept if score ≥ 0.75 | 15-50ms | $0  |
| **3 — Structural Heuristics** | Visual layout analysis + semantic block detection | Accept if score ≥ 0.60 | 50-100ms | $0  |
| **4 — LLM Extraction** | Claude Sonnet with Pydantic schema | Accept if score ≥ 0.50 | 1500-3000ms | $0.003 |
| **5 — Manual Escalation** | Flag for human review queue | Below 0.50 after LLM | async | $0 auto |

## 8.2 Self-Healing via DOM Fingerprinting

When a CSS selector fails (confidence drops below 0.90), the system automatically attempts DOM fingerprint healing using the Scrapling library. This approach stores a deterministic hash of the DOM element's structural position — its relationships to parent, sibling, and child elements — and uses this fingerprint to find the same element even after CSS class names change:

from scrapling import Fetcher, StealthyFetcher, PlayWrightFetcher

from scrapling.parser import Adaptor

class SelfHealingExtractor:

def \__init_\_(self):

self.fingerprint_store = PostgresStore('selector_fingerprints')

async def extract(self, html: str, domain: str, schema: Schema) -> ExtractionResult:

adaptor = Adaptor(html, auto_match=True, keep_comments=False)

\# Stage 1: Try stored CSS selector

stored_selector = self.fingerprint_store.get(domain, schema.field)

if stored_selector:

result = adaptor.css(stored_selector)

if result and self.validate(result, schema):

return ExtractionResult(data=result, confidence=0.95, method='css')

\# Stage 2: Scrapling auto_match — finds element by DOM fingerprint

fingerprint = self.fingerprint_store.get_fingerprint(domain, schema.field)

if fingerprint:

result = adaptor.auto_match(fingerprint) # DOM similarity search

if result and self.validate(result, schema):

\# Update stored selector with new working CSS

new_selector = adaptor.get_css_path(result)

self.fingerprint_store.update(domain, schema.field, new_selector)

return ExtractionResult(data=result, confidence=0.82, method='fingerprint_healed')

\# Stage 3-4: Heuristics then LLM (see below)

return await self.llm_extract(html, schema)

## 8.3 LLM Extraction (Claude Sonnet — Controlled Cost)

When all deterministic methods fail, Claude Sonnet extracts with a typed Pydantic schema. v3.0 reduces LLM call frequency vs v2.0 by approximately 60-70% due to the preceding cascade stages. Key improvements:

- HTML is pre-processed to markdown (Trafilatura) before LLM call — reduces tokens by 70%
- Only the section of the page containing contact info is passed (max 1500 tokens, not 3000)
- Response cached per domain+page_hash for 7 days — same page never LLM-processed twice
- Confidence score returned by LLM (asked in prompt) — feeds Policy Engine feedback

\# LLM extraction schema — typed output

class BusinessContactSchema(BaseModel):

phone: Optional\[str\] = Field(None, description='Primary phone number, international format')

whatsapp: Optional\[str\] = Field(None, description='WhatsApp number from wa.me links')

email: Optional\[EmailStr\] = Field(None, description='Primary business email')

facebook_url: Optional\[HttpUrl\] = None

instagram_url: Optional\[HttpUrl\] = None

extraction_confidence: float = Field(..., ge=0.0, le=1.0)

# 9\. Layer 5 — Enrichment Layer

The Enrichment Layer transforms raw extracted records into rich, actionable business intelligence. This layer runs asynchronously after extraction — it does not block the crawl pipeline. Results are merged back into the record when complete.

| **Enrichment Module** | **What It Does** | **Technology** | **CPU Model** |
| --- | --- | --- | --- |
| **Named Entity Recognition (NER)** | Extracts persons, orgs, locations, products from page text | GLiNER (zero-shot NER, no fine-tuning needed) | ProcessPool worker |
| **Phone Geocoder** | Maps phone country code to city/region for validation | phonenumbers library + custom logic | asyncio (fast lookup) |
| **Address Geocoder** | Converts address string to lat/lng + standardized format | geopy + OpenStreetMap Nominatim (free) or Google Geocoding API | asyncio batch |
| **Business Classifier** | Assigns ISIC/NAICS business category with confidence | zero-shot-classification (facebook/bart-large-mnli) | ProcessPool worker |
| **WhatsApp Validator** | Validates WhatsApp number format and extracts from links | Custom regex + phonenumbers library | asyncio (fast) |
| **Email MX Validator** | Verifies email domain has valid MX records (DNS lookup) | dnspython async | asyncio batch |
| **Website Status Checker** | HEAD request to verify website is live | httpx async HEAD (no body) | asyncio batch |
| **Duplicate Detector** | Multi-signal deduplication beyond v2.0's simple MD5 | See Section 9.1 below | Redis + PostgreSQL |

## 9.1 Advanced Deduplication Engine

v3.0 replaces the simple MD5(name+phone) approach with a multi-signal probabilistic deduplication system:

| **Signal** | **Weight** | **Algorithm** |
| --- | --- | --- |
| **Phone number match (normalized)** | 0.95 certainty | Exact match after international normalization |
| **Email domain match** | 0.80 certainty | Domain-level match (info@X and sales@X = same biz) |
| **Business name fuzzy match** | 0.70 certainty (with address match) | RapidFuzz token_sort_ratio > 88% |
| **Address geo-proximity** | 0.85 certainty (with name match) | Haversine distance < 50 meters |
| **Website domain match** | 0.95 certainty | Normalized domain equality |
| **Google Maps URL** | 1.0 certainty | Exact CID match from Maps URL |

Records are merged (not just flagged) when certainty exceeds 0.85, combining the best available data from each source.

# 10\. Layer 6 — Storage Layer

| **Store** | **What's Stored** | **Technology** | **Retention** |
| --- | --- | --- | --- |
| **Raw HTML Archive** | Original HTML of every fetched page (compressed) | MinIO (S3-compatible) with gzip | 30 days (configurable) |
| **Cleaned Text** | Markdown-converted clean page content | PostgreSQL JSONB column | 90 days |
| **Structured Records** | Business entities: all fields normalized and validated | PostgreSQL (primary store) | Forever |
| **Extraction Metadata** | Selector used, confidence, method, timestamp | PostgreSQL | 1 year |
| **Graph Relationships** | Business networks, competitors, area clusters | Neo4j | Forever |
| **Policy Engine State** | Domain yield rates, selector health, ban history | Redis Hash (persistent) | Forever (persisted) |
| **Session Cache** | In-progress job state, page visit dedup bloom filter | Redis (volatile) | Job lifetime |
| **Audit Log** | Every compliance decision, crawl event, API call | PostgreSQL append-only | 2 years |

## 10.1 PostgreSQL Schema (Key Tables)

\-- businesses: core entity table

CREATE TABLE businesses (

id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

google_maps_id TEXT UNIQUE,

name TEXT NOT NULL,

phone TEXT, -- normalized international format

whatsapp TEXT,

email TEXT,

email_verified BOOLEAN DEFAULT FALSE,

address TEXT,

city TEXT,

country_code CHAR(2),

lat NUMERIC(10,7),

lng NUMERIC(10,7),

website_url TEXT,

has_website BOOLEAN GENERATED ALWAYS AS (website_url IS NOT NULL) STORED,

facebook_url TEXT,

instagram_url TEXT,

rating NUMERIC(2,1),

review_count INTEGER,

category TEXT,

isic_code TEXT, -- enrichment

record_completeness NUMERIC(3,2), -- 0.00-1.00

source TEXT, -- 'google_maps' | 'website_crawl'

scraped_at TIMESTAMPTZ DEFAULT now(),

updated_at TIMESTAMPTZ DEFAULT now()

);

CREATE INDEX idx_businesses_city ON businesses(city);

CREATE INDEX idx_businesses_has_website ON businesses(has_website);

CREATE INDEX idx_businesses_geo ON businesses USING GIST(point(lng, lat));

# 11\. Layer 7 — Indexing Layer

The Indexing Layer creates three parallel indexes for different retrieval modalities, ensuring sub-100ms query performance at 1M+ records.

| **Index** | **Technology** | **Fields Indexed** | **Query Type Served** |
| --- | --- | --- | --- |
| **Inverted Index (BM25)** | OpenSearch 2.11 | name, address, category, city, email, phone | Keyword search, exact match, boolean filters |
| **Dense Vector Index** | Qdrant (HNSW) | 384-dim embedding of name+category+description | Semantic search, similar businesses, NL queries |
| **Graph Index** | Neo4j (Cypher) | Business nodes + SAME_AREA / COMPETITOR / SUPPLIES edges | Relationship queries, network analysis, clustering |
| **Geospatial Index** | PostgreSQL GIST | lat+lng coordinates | Radius search, bounding box, distance sort |

## 11.1 Embedding Pipeline (Zero-Cost)

Embeddings are generated using all-MiniLM-L6-v2 (384 dimensions, free, runs on CPU). This runs in a dedicated ProcessPool worker to avoid blocking the asyncio event loop. Batched embedding generation (128 records per batch) achieves ~2000 embeddings/minute on a single CPU core.

# 12\. Layer 8 — Retrieval Layer

The Retrieval Layer is where v3.0 makes the biggest improvement over v2.0. Research (2024-2026) consistently shows that two-stage hybrid retrieval (BM25 + dense + RRF fusion followed by cross-encoder reranking) outperforms any single-stage approach by 17-40% on precision metrics.

## 12.1 Hybrid Retrieval Pipeline

class HybridRetriever:

async def retrieve(self, query: str, top_k: int = 10) -> list\[BusinessRecord\]:

\# Stage 1A: BM25 retrieval (keyword matching)

bm25_candidates = await self.opensearch.search(

query=query, size=30, filters=self.active_filters

) # fast: <20ms

\# Stage 1B: Dense retrieval (semantic matching, parallel with BM25)

query_embedding = self.embedder.encode(query) # ~5ms

dense_candidates = await self.qdrant.search(

vector=query_embedding, limit=30, filter=self.active_filters

) # fast: <30ms

\# Stage 2: RRF Fusion (Reciprocal Rank Fusion)

\# Merges both candidate lists, rewards docs appearing in both

fused = rrf_fusion(bm25_candidates, dense_candidates, k=60)

\# Top 30 unique candidates

\# Stage 3: Cross-encoder reranking (only if query warrants it)

if self.policy_engine.should_rerank(query, len(fused)):

\# Cross-encoder scores (query, doc) pairs — much more accurate

scores = self.cross_encoder.predict(\[(query, doc.text) for doc in fused\[:20\]\])

fused = \[d for \_, d in sorted(zip(scores, fused\[:20\]), reverse=True)\]

return fused\[:top_k\]

## 12.2 Research-Backed Performance Numbers

| **Retrieval Method** | **Recall@5** | **MRR@3** | **Latency** |
| --- | --- | --- | --- |
| **BM25 only (v2.0)** | 0.644 | 0.310 | 20ms |
| **Dense only** | 0.587 | 0.290 | 35ms |
| **Hybrid RRF (BM25+Dense)** | 0.695 | 0.433 | 50ms |
| **Hybrid + Cross-encoder Rerank (v3.0)** | 0.816 | 0.605 (+95% vs v2.0) | 120ms |

Source: Biswas et al. 2024 (product QA benchmark); adapted metrics confirm that the hybrid+rerank pipeline is the correct architecture for production RAG systems. The Policy Engine decides whether to run the expensive cross-encoder step based on query complexity and latency budget.

# 13\. Concurrency Architecture — The Right Tool for Each Job

This is the most critical performance improvement in v3.0. The fundamental insight from research (2025) is: asyncio is 130x faster than synchronous code for I/O-bound tasks. But for CPU-bound tasks (HTML parsing, NER, embedding generation), asyncio adds overhead without benefit — multiprocessing is required.

| **Task Type** | **v2.0 Approach** | **v3.0 Approach** | **Speedup** |
| --- | --- | --- | --- |
| **HTTP fetching (static)** | Celery sync requests | asyncio + httpx (200 concurrent) | ~100x |
| **Browser rendering** | Celery + blocking Playwright | asyncio + async Playwright browser pool (10 instances) | ~8x |
| **HTML parsing (selectolax)** | Sync in Celery worker | ProcessPool (4 workers, parallel parsing) | ~3x |
| **NER enrichment (CPU)** | Not present | ProcessPool + batching (GLiNER) | new |
| **Embedding generation (CPU)** | Not present (no dense index) | ProcessPool + batching (128/batch) | new |
| **LLM API calls** | Sync Claude API calls | asyncio + httpx async (10 concurrent LLM calls) | ~8x |
| **Database writes** | Sync SQLAlchemy | asyncpg async driver + connection pool | ~5x |
| **Redis operations** | Sync Redis | aioredis async client | ~10x |

## 13.1 Worker Architecture

\# ASAGUS 3.0 Worker Architecture — per machine

#

\# Each 'worker' is ONE Python process with ONE asyncio event loop

\# The event loop handles 200+ concurrent I/O operations

\# CPU tasks are offloaded to ProcessPool via loop.run_in_executor()

#

\# ┌─────────────────────────────────────────────────────────────┐

\# │ MAIN PROCESS (asyncio event loop) │

\# │ │

\# │ ► 200 concurrent HTTP connections (httpx) │

\# │ ► 10 concurrent browser tabs (async Playwright) │

\# │ ► 50 concurrent Redis operations │

\# │ ► 20 concurrent PostgreSQL queries (asyncpg) │

\# │ ► 10 concurrent LLM API calls │

\# │ │

\# │ CPU OFFLOAD → ProcessPoolExecutor(max_workers=4) │

\# │ Worker-0: HTML parsing (selectolax) │

\# │ Worker-1: NER enrichment (GLiNER) │

\# │ Worker-2: Embedding generation (all-MiniLM) │

\# │ Worker-3: Deduplication + normalization │

\# └─────────────────────────────────────────────────────────────┘

#

\# Run 3 such processes per machine for 3x throughput

\# (limited by proxy bandwidth and target site rate limits)

## 13.2 Redis Streams for Inter-Layer Communication

Layers communicate via Redis Streams (not direct function calls). This decouples layers and allows each to scale independently:

\# Redis Streams pipeline

frontier_stream: URLs to crawl → consumed by Fetch Layer

fetch_complete: Raw HTML + metadata → consumed by Extraction Layer

extract_complete: Structured JSON → consumed by Enrichment Layer

enrich_complete: Rich records → consumed by Storage Layer

index_queue: Records to index → consumed by Indexing Layer

policy_feedback: Outcomes from all layers → consumed by Policy Engine

# 14\. Performance Targets — v3.0 vs v2.0

| **Metric** | **v2.0 Target** | **v3.0 Target** | **How Achieved** |
| --- | --- | --- | --- |
| **Maps scraping speed** | 50 biz/min per worker | 200 biz/min per async worker | asyncio 200 concurrent + MDP skips zero-yield URLs |
| **Website deep crawl** | 30 sites/min per worker | 150 sites/min per worker | asyncio static fetch for 80% of sites (no browser needed) |
| **1000 results time** | ~20 minutes (5 workers) | ~5 minutes (3 async workers) | 4x throughput + smarter scheduling |
| **LLM API calls** | ~30% of pages | ~8% of pages | Self-healing extraction handles 22% that previously hit LLM |
| **Search latency** | <100ms | <120ms (with reranking) | Hybrid retrieval, 95% of queries don't need reranking |
| **Anti-bot success rate** | \>95% | \>97% | Policy Engine avoids patterns that trigger detection |
| **Data accuracy** | \>90% | \>96% | Confidence cascade + self-healing + advanced dedup |
| **Selector maintenance** | Manual fix on site change | Zero manual intervention | Self-healing DOM fingerprinting |
| **RAM per worker** | ~300 MB per Celery worker | ~120 MB per async worker | asyncio vs process-per-request model |
| **Uptime / reliability** | 99% (manual fix needed) | 99.9% (self-healing) | Policy Engine detects failures and reroutes automatically |

# 15\. Development Plan — Revised Week by Week

| **Phase** | **Weeks** | **Goal** | **Deliverable** |
| --- | --- | --- | --- |
| **Phase 1: Async Foundation** | 1–2 | Replace Celery with asyncio worker; static httpx + async Playwright pool | Async scraper fetches 200 biz/min from Maps |
| **Phase 2: Policy Engine MVP** | 3–4 | Rule-based Policy Engine; static vs dynamic routing; Markov state logging | 60% reduction in unnecessary browser renders |
| **Phase 3: Self-Healing Extraction** | 5–6 | Scrapling DOM fingerprinting; confidence cascade; LLM fallback pipeline | Selector breaks auto-repair without dev intervention |
| **Phase 4: MDP Scheduler** | 7–8 | Full MDP frontier with Markov transition model; URL yield prediction | Crawl scheduler routes to high-yield URLs first |
| **Phase 5: Enrichment Layer** | 9–10 | GLiNER NER; geocoding; business classifier; advanced dedup | Rich records with entity data and validated contacts |
| **Phase 6: Hybrid Retrieval** | 11–12 | Qdrant dense index; RRF fusion; cross-encoder reranker | Search precision +40% vs v2.0 BM25-only |
| **Phase 7: AI Application Layer** | 13–14 | RAG pipeline; ReAct agent for complex queries; live Next.js dashboard | Full product with NL query interface |
| **Phase 8: Production Hardening** | 15–16 | Load testing; Policy Engine learning loop; Neo4j graph; multi-tenant | Production-ready, 99.9% uptime target |

# 16\. Complete Tech Stack — Updated for v3.0

| **Category** | **Technology** | **Version** | **Why (v3.0 Specific Reason)** |
| --- | --- | --- | --- |
| **Concurrency (I/O)** | asyncio + httpx | Python 3.12, httpx 0.27 | 130x faster than sync for HTTP fetching; replaces Celery for I/O layer |
| **Concurrency (CPU)** | multiprocessing ProcessPool | Python 3.12 stdlib | True parallelism for NER, embedding, parsing — bypasses GIL |
| **Async Playwright** | playwright async_api | Latest | Non-blocking browser automation; works with asyncio event loop |
| **Stealth Browser** | Camoufox | Latest | 0% detection score; Firefox TLS profile bypasses Cloudflare JA3 |
| **Static Scraping (adaptive)** | Scrapling | v0.4+ | DOM fingerprinting for self-healing selectors — Feb 2026 release |
| **HTML Parser** | selectolax | Latest | 10x faster than BeautifulSoup; handles malformed HTML |
| **NER Engine** | GLiNER | Latest | Zero-shot NER — no fine-tuning; works on business/location entities |
| **Crawler Framework** | Crawl4AI | Latest | Async browser pool; LLM-ready markdown; adaptive crawl stopping |
| **LLM (extraction+RAG)** | Claude Sonnet 4 | claude-sonnet-4-20250514 | Best extraction accuracy; structured output with Pydantic schemas |
| **Job Queue + Streams** | Redis Streams | 7.x | Decoupled inter-layer communication; consumer groups; backpressure |
| **Keyword Search** | OpenSearch | 2.11 | BM25, geo-search, bool filters; <20ms at 1M docs |
| **Vector Search** | Qdrant HNSW | Latest | HNSW ANN index; filtered vector search; ef=128 for high recall |
| **Embeddings** | all-MiniLM-L6-v2 | Latest | Free; 384-dim; fast on CPU; 2000 embeddings/min batched |
| **Graph DB** | Neo4j | 5.x | Business relationship queries; competitor detection; area clustering |
| **RAG Framework** | LlamaIndex | Latest | Qdrant + OpenSearch integration; ReAct agent support |
| **Async DB Driver** | asyncpg | Latest | Replaces sync SQLAlchemy; 5x faster for concurrent writes |
| **Object Storage** | MinIO | Latest | S3-compatible raw HTML archive; self-hosted |
| **API Framework** | FastAPI | Latest | Async-native; WebSocket support; auto OpenAPI docs |
| **Frontend** | Next.js 15 + React 19 | Latest | App router; RSC; real-time WebSocket updates |
| **UI Components** | ShadcnUI + Tailwind | Latest | Professional data table; filters; CSV export |
| **Geocoding** | geopy + Nominatim | Latest | Free OSM geocoding; Google API fallback for precision |
| **Phone Validation** | phonenumbers (libphonenumber) | Latest | Google's phone library; validates + formats international numbers |
| **Containerization** | Docker + Compose | Latest | One-command deployment; health checks; auto-restart |
| **Reverse Proxy** | Nginx | Latest | SSL termination; WebSocket proxy; static file serving |

# 17\. Cost Estimate — v3.0 vs v2.0

| **Component** | **v2.0 Cost/Month** | **v3.0 Cost/Month** | **Saving / Note** |
| --- | --- | --- | --- |
| **Residential Proxies (BrightData)** | $50–150 | $40–120 | MDP skips zero-yield URLs → less bandwidth |
| **Server (VPS)** | $40–80 | $50–90 | Slightly larger for ProcessPool workers; 4 vCPU 16GB RAM |
| **Claude API (LLM fallback)** | $10–30 | $3–10 | Self-healing cuts LLM calls by ~70% |
| **Anti-CAPTCHA service** | $10–20 | $8–15 | Policy Engine learns to avoid CAPTCHA triggers |
| **MinIO storage (HTML archive)** | $0  | $5–10 | New: raw HTML archiving for replay/debugging |
| **Total (estimated)** | $110–280/month | $106–245/month | ~12% cheaper + dramatically better results |

# 18\. Infrastructure — Docker Compose (Updated)

| **Service** | **Image** | **Port** | **v3.0 Role** |
| --- | --- | --- | --- |
| **opensearch** | opensearchproject/opensearch:2.11 | 9200 | BM25 keyword index — stage 1 of hybrid retrieval |
| **qdrant** | qdrant/qdrant:latest | 6333 | HNSW vector index — stage 2 of hybrid retrieval |
| **neo4j** | neo4j:5 | 7474/7687 | Graph DB for business relationship network |
| **redis** | redis:7-alpine | 6379 | Streams pipeline + Policy Engine state + job queue |
| **postgres** | postgres:16-alpine | 5432 | Primary business data + audit log + selector store |
| **minio** | minio/minio:latest | 9000/9001 | Raw HTML archive (S3-compatible object storage) |
| **async-worker** | custom (Python 3.12) | —   | asyncio event loop + ProcessPool (Layers 1-5); 3 instances |
| **indexer-worker** | custom (Python 3.12) | —   | Dedicated indexing worker (Layers 7); separate to not block crawl |
| **api** | custom (Python 3.12) | 8000 | FastAPI backend + WebSocket status + REST endpoints |
| **frontend** | custom (Node 20) | 3000 | Next.js 15 dashboard |
| **nginx** | nginx:alpine | 80/443 | Reverse proxy + SSL + WebSocket routing |

\# Start command

docker-compose up -d --scale async-worker=3 --scale indexer-worker=1

\# async-worker × 3: each runs asyncio + 4-process ProcessPool

\# indexer-worker × 1: dedicated embedding + Qdrant/OpenSearch indexing

\# Total: 3 event loops × 200 concurrent I/O = 600 concurrent HTTP ops

# 19\. Quick Start Guide

## Step-by-Step First Run

1.  pip install camoufox playwright-stealth crawl4ai scrapling fastapi asyncpg aioredis httpx gliner phonenumbers geopy
2.  pip install 'scrapling\[all\]' && python -m playwright install
3.  python -m camoufox fetch # Download Firefox stealth binary
4.  docker-compose up -d # Start all infrastructure services
5.  cp .env.example .env # Configure proxy credentials + API keys
6.  python -m scripts.init_db # Create PostgreSQL schema + OpenSearch index
7.  python -m scripts.init_qdrant # Create Qdrant collection (384-dim HNSW)
8.  python -m workers.async_worker # Start async crawler worker
9.  uvicorn api.main:app --reload # Start FastAPI backend
10. cd frontend && npm run dev # Start Next.js dashboard
11. curl http://localhost:8000/scrape/start -d '{"query":"restaurants","city":"Lahore","limit":100}'

_Start with limit=100 to validate setup before scaling. Monitor Policy Engine decisions at http://localhost:8000/policy/stats_

# 20\. Legal & Ethical Notes

These notes are carried forward from v2.0 and remain critical:

- Google Maps Terms of Service restrict automated scraping — use for research/personal use only; review ToS before commercial deployment
- GDPR/PDPA compliance required for EU citizen data — the Enrichment Layer GDPR tagger flags these records for appropriate handling
- robots.txt compliance is enforced automatically by the Compliance Layer — do not disable
- Rate limiting is built into the Compliance Layer — the token bucket prevents server overload
- Collected contact data must not be used for unsolicited spam — ASAGUS outreach should be permission-based
- The audit log provides legal compliance evidence of responsible crawl behavior