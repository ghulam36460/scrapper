# ASAGUS Scraper v3 — True Status, Gap Analysis & Production Plan

**Date:** 2026-06-30
**Purpose:** A single, honest source of truth that maps what the three design
documents (`ASAGUS scrapper _3_0_v2.md`, `antibot.md`, `LIBRARY_USAGE_ANALYSIS.md`)
**describe** against what the code **actually implements**, what is integrated,
what is missing, and what to fix to reach production.

> **Important correction to the original assumption.** The brief said
> "only ~20% of the scraper is implemented and 80% is not." After reading the
> code, that is **not accurate**. The core pipeline is largely built and the
> backend test suite passes (69/69 with full deps). The real gap is **not**
> "80% unwritten" — it is:
> 1. A handful of **packaging / dependency bugs** that block a clean install.
> 2. **Download tools are mostly stubs** (only maps-scraper / outreach-scraper
>    have real scraping code; the rest report "prepared" without scraping).
> 3. **Advanced anti-bot tools (Camoufox, Patchright, nodriver) are coded as
>    integration seams but not installed/active** — exactly what
>    `LIBRARY_USAGE_ANALYSIS.md` already says.
> 4. **No live network run has been validated** (offline mode yields 0 records
>    by design).
>
> A more realistic split is roughly **70-75% implemented**, **~15% partially
> integrated (needs deps/binaries)**, and **~10% stub/missing**.

---

## 1. What the three documents say

### 1.1 `ASAGUS scrapper _3_0_v2.md` — the architecture blueprint
A full v3.0 design for an "Intelligent Scraping System":

- **Layer 0 — Policy Engine (brain):** rule layer + Bayesian classifier +
  feedback loop; routes crawl/skip, static/dynamic, CSS/LLM, index decisions.
- **Layer 1 — Crawl Control Plane:** multi-tier frontier + Markov Decision
  Process (MDP) scheduler, three-phase cold-start (heuristic → hybrid → full MDP),
  transition-prior matrix per URL type.
- **Layer 2 — Compliance:** robots.txt parser+cache, token-bucket rate limiter,
  allow/blocklist, audit log, GDPR tagger.
- **Layer 3 — Fetch:** static-first (httpx / curl-cffi) vs dynamic
  (Playwright/Camoufox) routing, proxy pool tiers.
- **Layer 4 — Extraction:** self-healing cascade CSS → DOM fingerprint
  (Scrapling) → structural heuristics → LLM, with confidence scoring.
- **Layer 5 — Enrichment:** NER (GLiNER), geocoding, phone validation,
  classification, multi-signal dedup.
- **Layer 6 — Storage:** MinIO + PostgreSQL + Neo4j + Redis.
- **Layer 7 — Indexing:** OpenSearch BM25 + Qdrant dense + geospatial.
- **Layer 8 — Retrieval:** hybrid BM25+dense+RRF + cross-encoder rerank.
- **Layer 9 — AI App:** RAG, ReAct agent, Next.js dashboard.
- Plus: failure-mode/recovery map, observability matrix, cost model, Docker
  Compose with 11 services, 16-week dev plan, legal/ethical notes.

### 1.2 `antibot.md` — the anti-bot research monograph
A reference document (not a build spec) describing the **5-layer detection
arms race**:

- **Layer 1** core automation (Selenium/Playwright/nodriver/httpx/curl-cffi),
  the CDP detection problem.
- **Layer 2** stealth: JS-shim (weak) vs binary-patch (strong: Camoufox,
  Patchright, CloakBrowser).
- **Layer 3** TLS/network fingerprint (JA3/JA4, HTTP/2 SETTINGS, curl-cffi).
- **Layer 4** browser/DOM fingerprint (Canvas, WebGL, AudioContext, hardware).
- **Layer 5** behavioral biometrics (Sigma Log-Normal mouse model, Fitts' Law,
  inter-keystroke timing).
- CAPTCHA chapter (reCAPTCHA/hCaptcha/Turnstile) and a theoretical multi-layer
  evasion threat model — explicitly framed as **educational**.

### 1.3 `LIBRARY_USAGE_ANALYSIS.md` — self-audit of anti-bot coverage
The project's own audit, scoring implementation **7.5/10**:

- **Strong / implemented:** curl-cffi TLS (Layer 3), behavioral math models
  (Layer 5), native C/C++ architecture (Layer 6), Playwright (Layer 1),
  custom JS fingerprint spoofing (Layer 4).
- **Weak / not integrated:** Layer 2 binary-patch stealth — **Camoufox,
  Patchright, nodriver, CloakBrowser are mentioned but NOT installed/active**;
  no real CAPTCHA solver.

**Key takeaway:** Documents 2 and 3 already admit the biggest gap is binary-patch
stealth integration. The code confirms this exactly.

---

## 2. What the code ACTUALLY implements (verified)

Location: `asagus-scraper-v3/backend/asagus/`. The main orchestrator
`main.py::run_job` is ~1,215 lines and genuinely wires the layers end to end.

| Blueprint layer | Code file(s) | Implementation reality |
|---|---|---|
| 0 Policy Engine | `layers/policy.py` | **Real.** Rule layer + Naive-Bayes log-likelihood classifier + per-domain feedback moving averages + quality estimator. Not a stub. |
| 1 Crawl/MDP | `layers/crawl_control.py` | **Real & deep.** Full MDP: state space generation, value iteration, action transitions, UCB online learning, 3-phase cold-start, transition priors per URL type. |
| 2 Compliance | `layers/compliance.py` | **Real.** robots cache, token bucket, allow/blocklist, async checks. |
| 3 Fetch | `layers/fetch.py`, `browser.py`, `proxy*.py` | **Real.** Static path uses curl-cffi (`impersonate=chrome124`) → Scrapling → httpx fallback; dynamic path via browser pool; **escalation ladder** (static→dynamic→stealth→saved-session); offline preview mode. |
| 4 Extraction | `layers/extraction.py`, `external_adapters.py`, `lead_intelligence.py` | **Real & substantial.** CSS/JSON-LD/regex + Scrapy/parsel + Scrapling adapters, Cloudflare email decode, obfuscated-email parse, decision-maker detection, DOM-fingerprint healing, structural heuristics, LLM fallback. |
| 5 Enrichment | `layers/enrichment.py`, `geoint.py`, `nlp_intelligence.py` | **Real.** Phone normalization (phonenumbers), dedup scoring, geocoding hook, NLP intelligence. |
| 6 Storage | `layers/storage.py`, `services/runtime.py`, `db/` | **Real but local-first.** JSON/runtime persistence + raw-HTML archive; Postgres/MinIO/Neo4j are **optional** and disabled in local mode. |
| 7 Indexing | `layers/indexing.py`, `search_index.py` | **Real (in-process).** Index/queue logic present; OpenSearch/Qdrant optional. |
| 8 Retrieval | `layers/retrieval.py` | **Real.** Hybrid + rerank-decision logic present. |
| 9 AI App | `routers/*`, `frontend/` | **Real.** FastAPI routers + Next.js 15 dashboard that builds. |
| Anti-bot 1-6 | `layers/antibot_layer1..6_*.py`, `antibot_orchestrator.py` | **Coded as orchestrated layers** with config presets, TLS profiles, stealth approaches, behavior models, native C/C++ sources. |

**Anti-bot vs `LIBRARY_USAGE_ANALYSIS.md` (verified against code):**
- curl-cffi TLS impersonation — **active** in `fetch.py`. ✅
- Behavioral models (Sigma Log-Normal, Fitts) — **present** in
  `human_behavior.py` / `antibot_layer5_behavior.py`. ✅
- Native C/C++ layer — **source files + compiler wrapper present**, compile
  status unverified. ⚠️
- Camoufox / Patchright / nodriver — **integration modules exist**
  (`camoufox_integration.py`, `patchright_integration.py`,
  `nodriver_integration.py`) and `fetch.py` checks `available_engines()`, **but
  the packages/binaries are not installed**, so these engines are inactive. ⚠️

---

## 3. Download tools — integration reality

Mechanism: `services/tools_runner.py` registers 11 tools and launches each as a
subprocess via `Download/asagus_tool_launcher.py` or a per-tool
`asagus_adapter.py`. In MAX mode, `launch_max_mode_tools()` runs them in
parallel and the backend also uses **library-level adapters** (Scrapy/parsel,
Scrapling) directly inside extraction.

| Tool | Folder | Integration state |
|---|---|---|
| maps-scraper | `scrapping-tool-of-maps-main` | **Real backend** (`backend/enhanced_scraper.py`) exists, BUT its `asagus_adapter.py` is **deleted** and `run-asagus.sh` points to the **stub launcher** → real code currently bypassed. ❌ inconsistent |
| outreach-scraper | `scrapping-for-outreach-tool-main` | Has `asagus_adapter.py` + real backend. ⚠️ verify live |
| scrapy | `scrapy-master` | Used as a **library adapter** (parsel/Selector) in extraction ✅; standalone adapter is a **stub** (returns "prepared"). |
| scrapling | `Scrapling-main` | Used as **library adapter** (parser + optional fetch) ✅ when installed. |
| firecrawl | `firecrawl-main` | **Stub** adapter; needs API key; Node app unbuilt. ❌ |
| scrapegraph-ai | `Scrapegraph-ai-main` | **Optional** LLM path; off unless installed/configured. ❌ |
| agent-reach | `Agent-Reach-main` | Enrichment service wired (`agent_reach_enrichment.py`) with auto-install attempt; runtime depends on its deps. ⚠️ |
| maxun | `maxun-develop` | Node app, **no node_modules**, stub adapter. ❌ |
| whatsapp-detector | `whatsapp-number-detector-main` | Node app, **no node_modules**, stub adapter. ❌ |
| outreach / outreach-system | `outreach-main` / `outreach-system-main` | Stub/optional. ❌ |

**Summary:** Tools are **wired to launch**, but most are **stubs** that report
status without scraping. Only the maps/outreach scrapers contain real logic, and
the maps one is currently mis-wired to the stub launcher. The blueprint-relevant
scraping (Scrapy/parsel + Scrapling) **is** genuinely integrated as in-process
libraries.

---

## 4. Environment & test verification (already run)

- Python 3.13.12, Node 24.x, Docker present. ✅
- Backend imports after installing `beautifulsoup4`. ✅
- **All 69 backend tests pass** with full deps (scrapy, scrapling) installed. ✅
- Root tests (`test_noise_reduction.py`, `test_prompt_requirements.py`) pass. ✅
- Frontend `npm install` + `npm run build` succeed. ✅
- Heavy anti-bot packages (camoufox, nodriver, patchright,
  undetected-chromedriver) install on 3.13. ✅
- End-to-end **offline** job completes (`status=completed`) but yields **0
  records** — expected, offline returns a preview page only. ⚠️
- Playwright browsers **not installed**; Node tools have **no node_modules**. ❌

---

## 5. Confirmed defects to fix (in priority order)

1. **Missing dep `beautifulsoup4`** — imported by `extraction.py`, absent from
   both `requirements.txt` and `requirements-local.txt`. **Blocks clean install.**
2. **`requirements-local.txt` omits `scrapy` + `scrapling`** — causes 2 test
   failures on the documented local setup.
3. **maps-scraper mis-wired** — restore `asagus_adapter.py` and fix
   `run-asagus.sh` to call the adapter, not the stub launcher.
4. **Download stub tools** — decide per tool: implement real scraping, or remove
   from the MAX-mode launch list / mark clearly as optional.
5. **`Download/test_all_tools.sh` is buggy** — `set -e` + `((TESTED++))` aborts
   on first increment; also requires `jq` (not installed).
6. **Advanced stealth inactive** — install + activate Camoufox / Patchright /
   nodriver and run `playwright install`, or document them as optional tiers.
7. **No live-run validation** — run a real network-enabled job to prove actual
   data extraction + CSV/merge output.
8. **`jq` missing** — many scripts/commands depend on it.
9. **Optional infra disabled** — Postgres/Qdrant/OpenSearch/MinIO/Neo4j run only
   via Docker Compose; local mode is in-memory/JSON. Fine for dev, must be
   enabled+tested for production.

---

## 6. Production readiness plan (next chat)

**Phase A — Make install reproducible (fast):**
- Add `beautifulsoup4` to both requirements files; add `scrapy`/`scrapling` to
  local reqs. Pin versions. Re-run `pytest` → expect 69/69 with a clean venv.
- Add a one-shot setup script: venv + deps + `playwright install chromium` +
  `npm install` (frontend + Node tools) + install `jq`.

**Phase B — Fix tool integration:**
- Restore maps-scraper adapter + correct `run-asagus.sh`.
- Repair `test_all_tools.sh` (remove fragile arithmetic under `set -e`, drop the
  hard `jq` dependency or guard it).
- For each Download tool: classify **real / stub / drop**; only keep real ones in
  the MAX-mode launch set.

**Phase C — Validate live scraping (the real proof):**
- Run a small network-enabled job (e.g. limit=10) against a permitted target,
  confirm records persist, dedup works, and CSV merge produces clean output.
- Verify the escalation ladder and offline→online switch.

**Phase D — Activate anti-bot tiers (optional/legal-gated):**
- Install + smoke-test Camoufox, Patchright, nodriver; confirm
  `available_engines()` reports them and `fetch.py` selects them.
- Per `antibot.md`: keep CAPTCHA-bypass / hardware-attestation features
  **out of scope for now** (deferred, per the stated business decision).

**Phase E — Production hardening:**
- Bring up Docker Compose services (Postgres/Qdrant/OpenSearch/MinIO/Redis),
  point storage/indexing at them, run the documented `init_db` / `init_qdrant`.
- Load/soak test per blueprint Phase 8; wire observability metrics.

---

## 7. Scope explicitly DEFERRED (per business decision)

These are intentionally **dropped for now** and will be added later, in line with
each country's laws/regulations and after usage analysis:

- Any **CAPTCHA solving / anti-bot bypass that defeats access controls**.
- **Authenticated social scraping** (Instagram/Facebook private/ordinary
  accounts) and anything requiring credential-gated or ToS-restricted access.
- Hardware-attestation / Turnstile-PoW defeat (a cryptographic hard wall per
  `antibot.md`; not pursued).

**Goal restated:** a production-grade lead-discovery scraper that helps startups
find clients and decision-makers (e.g. CEOs/owners) and surface small e-commerce
businesses that are upgrade candidates — using **public** data and
**permission-based** outreach, with the restricted capabilities added later under
proper legal/compliance controls.

---

## 8. One-line verdict

The architecture in the blueprint is **mostly built and tested**, not 20% done.
To ship: fix the dependency/packaging bugs, repair/trim the Download-tool
integration, validate one real network run, and (optionally) activate the
binary-patch stealth tier. CAPTCHA/auth-gated scraping stays deferred by design.
