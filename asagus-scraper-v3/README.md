

## What Is Implemented

- 10-layer backend module layout matching the architecture document.
- FastAPI control plane with jobs, policy decisions, records, retrieval and LLM settings.
- GUI-first Next.js console for launching jobs, watching pipeline events, tracking progress, searching records and adding LLM keys.
- Bring-your-own LLM settings for Claude, OpenAI, API-key-only hosted model providers, OpenAI-compatible gateways and Ollama.
- Expanded provider registry for Claude, OpenAI, Azure OpenAI, Gemini, Mistral, Groq, Together, OpenRouter, NVIDIA NIM, DeepInfra, Cerebras, Fireworks, Hugging Face Router, Perplexity, Ollama and custom HTTP gateways.
- Strong MDP frontier scheduler with abstract Markov state buckets, action-specific transition probabilities, value iteration, Q-value policy selection, online rewards, UCB exploration, cold-start phases and frontier tiers.
- Async I/O + process-pool CPU execution contract for high-throughput fetching, extraction, scoring and graph work.
- DDGS metasearch discovery adapter for DuckDuckGo, Bing, Brave, Google, Startpage, Wikipedia and other supported engines.
- Contact-page and social-profile follow-up discovery for public business websites.
- Duplicate URL and record skipping across repeated runs in the same backend session.
- Playwright Chromium dynamic-render adapter behind the compliance and policy layers.
- Blocklist and honeypot detector with quarantine/audit/manual review flow.
- Hybrid retrieval stack: BM25, dense cosine fallback, learned-sparse expansion, late-interaction fallback, RRF fusion and graph-guided adapter points.
- Inverted index, TF-IDF, hash vector embeddings, ANN/LSH buckets, learning-to-rank features and cross-encoder reranking fallback.
- NLP intelligence for sentiment, NER, summaries, attention-style term weighting and contrastive embedding previews.
- Safe public-business OSINT helpers, DOM/CSS/XPath tooling, predictive analytics, GEOINT and guarded computer-vision adapters.
- Local-safe offline pipeline so first setup does not make hidden scraping requests.
- Docker Compose for Postgres, Redis, OpenSearch, Qdrant, Neo4j, MinIO, API, workers, frontend, Prometheus and Grafana.
- SQL schema for jobs, businesses, extraction metadata, policy feedback, audit log and graph candidates.

## Local Safety Default

`ENABLE_NETWORK_FETCH=false` is intentional. The first run exercises the whole pipeline using an offline preview page. Set it to `true` only when you are ready for real fetch behavior and have reviewed compliance, robots, rate limits and provider terms.

`ENABLE_SEARCH_DISCOVERY=false` is also intentional. Search-engine discovery uses the DDGS adapter only when explicitly enabled.

Blocked URLs, honeypots, hidden links and access challenges are quarantined for audit. The system does not automate bypassing, unlocking or evading access controls.

API session exploitation is not implemented. Only documented public APIs or owned OAuth/API keys are supported. Face identification and biometric recognition are disabled.

## Quick Start

```powershell
cd asagus-scraper-v3
Copy-Item .env.example .env
docker compose up -d --build
```

Open:

- Frontend: `http://localhost:3000`
- API docs: `http://localhost:8000/docs`
- Grafana: `http://localhost:3001`
- MinIO console: `http://localhost:9001`

Initialize optional stores:

```powershell
docker compose exec api python -m asagus.scripts.init_db
docker compose exec api python -m asagus.scripts.init_qdrant
```

## LLM Providers

The UI supports:

- `anthropic` for Claude keys.
- `openai` for OpenAI keys.
- `openai_compatible` for OpenRouter, Groq-compatible, Together-compatible or private gateways.
- `azure_openai`, `google`, `mistral`, `groq`, `together`, `openrouter`, `nvidia`, `deepinfra`, `cerebras`, `fireworks`, `huggingface`, `perplexity` and `custom_http` for direct provider selection with default base URLs.
- `ollama` for local models exposed through an OpenAI-compatible URL.
- `disabled` for deterministic extraction only.

Keys submitted through the GUI are kept in backend process memory and are masked in API responses. For production, wire the same interface to a proper encrypted secret vault.

## Implementation Map

| Blueprint Layer | Backend Module |
| --- | --- |
| 0 Policy Engine | `asagus.layers.policy` |
| 1 Crawl Control Plane | `asagus.layers.crawl_control` |
| 2 Compliance Layer | `asagus.layers.compliance` |
| 3 Fetch Layer | `asagus.layers.fetch` |
| 4 Extraction Layer | `asagus.layers.extraction` |
| 5 Enrichment Layer | `asagus.layers.enrichment` |
| 6 Storage Layer | `asagus.layers.storage` |
| 7 Indexing Layer | `asagus.layers.indexing` |
| 8 Retrieval Layer | `asagus.layers.retrieval` |
| 9 AI Application Layer | `asagus.layers.ai_app` |

## Next Engineering Steps

1. Replace local runtime storage with Postgres repositories and Redis Streams consumers.
2. Implement async Playwright/Camoufox browser pool behind `FetchLayer`.
3. Add Scrapling DOM fingerprints and selector health persistence.
4. Add Qdrant/OpenSearch indexing writes in `IndexingLayer`.
5. Add Neo4j graph edge materialization from `relationship_candidates`.
6. Add authentication and encrypted secret storage before shared deployment.
