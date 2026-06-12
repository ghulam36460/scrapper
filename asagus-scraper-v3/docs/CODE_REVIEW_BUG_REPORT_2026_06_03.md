# ASAGUS Scraper v3 Code Review Bug Report

Date: 2026-06-03  
Scope: Static read-only review of the requested architecture documents and first-party source code.  
Constraint: The app was not run, tests were not run, and no source code was changed during the review.

## Executive Summary

The project is not currently production-ready against the ASAGUS 3.0 blueprint. The repository contains a useful local/demo pipeline and many anti-bot modules, but the active runtime path is much simpler than the documentation claims.

Estimated implementation status from static review:

| Area | Approximate Status | Notes |
| --- | ---: | --- |
| Local/demo scraper pipeline | 45-55% | API job path can discover, fetch, extract, enrich, store locally, and search local records. |
| Blueprint production architecture | 25-35% | Redis Streams, production workers, hard persistence, full infra, and model-backed intelligence are mostly missing or optional best-effort. |
| Real anti-bot integration in active crawl path | 10-20% | Anti-bot modules exist, but active jobs use plain `FetchLayer` and headless Chromium. |
| Claimed extraction/data accuracy | Not measurable | No benchmark suite or validation data proves the documented 96% target. |
| Protected-site success likelihood | Low | Dynamic fetch uses normal headless Chromium and challenge pages are routed to manual review rather than handled. |

The largest gap is documentation drift: many docs claim "complete", "production-grade", "0% detection", "100% CAPTCHA accuracy", "6-layer anti-detection", and "Redis Streams architecture", while the actual job runner is an in-process local pipeline with several placeholder/adaptor components.

## Reviewed Inputs

Primary blueprint and supporting docs reviewed:

- `ASAGUS scrapper _3_0_v2.md`
- `LIBRARY_USAGE_ANALYSIS.md`
- `LAYER6_IMPLEMENTATION_SUMMARY.md`
- `IMPLEMENTATION_VISUAL_SUMMARY.txt`
- `IMPLEMENTATION_SUMMARY.md`
- `IMPLEMENTATION_COMPLETE.md`
- `COMPLETE_6_LAYER_ARCHITECTURE.txt`
- `antibot.md`
- `asagus-scraper-v3/README_LAYER6.md`
- `asagus-scraper-v3/README.md`
- `asagus-scraper-v3/DOCUMENTATION_INDEX.md`
- `asagus-scraper-v3/docs/*`
- `asagus-scraper-v3/backend/ANTIBOT_IMPLEMENTATION.md`
- `asagus-scraper-v3/backend/LAYER6_INTEGRATION.md`

Source areas reviewed:

- `asagus-scraper-v3/backend/asagus/main.py`
- `asagus-scraper-v3/backend/asagus/models.py`
- `asagus-scraper-v3/backend/asagus/config.py`
- `asagus-scraper-v3/backend/asagus/services/*`
- `asagus-scraper-v3/backend/asagus/layers/*`
- `asagus-scraper-v3/backend/asagus/workers/*`
- `asagus-scraper-v3/backend/asagus/db/schema.sql`
- `asagus-scraper-v3/backend/tests/*`

## Critical Bugs

### 1. `antibot_preset` is exposed but ignored

Severity: Critical  
Status: Not implemented in active job path

`ScrapeStartRequest` exposes `antibot_preset` with descriptions for `high-stealth`, `balanced`, and `high-speed`, but `run_job()` never reads or applies this setting.

Relevant files:

- `backend/asagus/models.py`
- `backend/asagus/main.py`
- `backend/asagus/layers/fetch.py`

Impact:

- Users can select an anti-bot preset and believe it is active when it is not.
- Documentation claims about Camoufox/Patchright/native stealth do not apply to normal scraping jobs.
- Protected targets will be handled by the default fetch/browser path.

Required fix:

- Wire `antibot_preset` into `run_job()`.
- Create or inject an anti-bot-aware fetch/browser strategy.
- Emit selected anti-bot strategy in job events so operators can verify it.

### 2. Dynamic fetch uses plain headless Chromium

Severity: Critical  
Status: Implemented as plain renderer, not anti-bot browser

The dynamic fetch path calls `ChromiumBrowserPool.render()`, which launches Playwright Chromium with `headless=True`. The browser pool explicitly reports `challenge_bypass: False`.

Relevant files:

- `backend/asagus/layers/browser.py`
- `backend/asagus/layers/fetch.py`
- `backend/asagus/main.py`

Impact:

- The active browser path has no Camoufox, Patchright, nodriver, Layer 4 fingerprint profile, Layer 5 behavior, or Layer 6 native patches.
- Sites with basic headless/CDP checks can detect it.
- The anti-bot documentation substantially overstates live behavior.

Required fix:

- Replace `ChromiumBrowserPool` usage with an orchestrator-aware browser pool or strategy abstraction.
- Support at least: plain safe browser, Patchright/Camoufox path, and HTTP-only curl-cffi path.
- Add an automated smoke test that verifies the selected preset changes the actual browser/client path.

### 3. AntiBotOrchestrator exists but is not integrated

Severity: Critical  
Status: Module exists; production path missing

`AntiBotOrchestrator` initializes multiple anti-bot layers and is used by examples/docs, but not by the real API job runner.

Relevant files:

- `backend/asagus/layers/antibot_orchestrator.py`
- `backend/examples/antibot_complete_example.py`
- `backend/asagus/main.py`

Impact:

- The codebase has two separate scraping concepts: documented orchestrator examples and the actual API job runner.
- Fixes made in anti-bot modules will not improve normal scraping unless explicitly wired in.

Required fix:

- Move browser and HTTP client creation behind a shared interface used by `FetchLayer`.
- Make `run_job()` pass the job preset/proxy/device settings to that interface.

### 4. High-speed/native preset configuration can be overridden by defaults

Severity: Critical  
Status: Bug in config mapping

`create_antibot_orchestrator_from_config()` maps only a subset of loaded configuration into `AntiBotConfig`. It does not pass `enable_native_layer` or `native_backend`. Because `AntiBotConfig.enable_native_layer` defaults to `True`, presets that intended to disable native support can still instantiate Layer 6.

Relevant file:

- `backend/asagus/layers/antibot_orchestrator.py`

Impact:

- Preset behavior is unreliable.
- "High-speed" mode can initialize native controllers unexpectedly.
- Documentation and runtime behavior diverge.

Required fix:

- Map all relevant global config fields into `AntiBotConfig`.
- Add tests for each preset verifying selected stealth approach, TLS fingerprint, device profile, behavioral flag, and native flag.

### 5. CAPTCHA solving is placeholder code

Severity: Critical  
Status: Not implemented despite documentation claims

Docs claim reCAPTCHA v2 100% accuracy and hCaptcha 95.9% accuracy, but the code logs placeholders and returns false unless real external models are added. Even with flags enabled, YOLOv8/hCaptcha solving logic is not implemented.

Relevant file:

- `backend/asagus/layers/captcha_solver.py`

Impact:

- CAPTCHA-protected flows will fail or go to manual review.
- Accuracy claims are not supported.
- Operators may assume legal/technical capability that does not exist.

Required fix:

- Either remove/soften accuracy claims or implement real provider/model integrations.
- Add unit tests for detection and integration tests for solver strategy selection.
- Make solver availability explicit in `/api/algorithm/state` or health output.

### 6. Layer 6 native implementation is mostly aspirational

Severity: Critical  
Status: Partial wrappers and native source exist; core behavior missing

Native Layer 6 contains wrappers and C/C++ files, but Linux browser patching returns failure, typo simulation is TODO, and `apply_native_patches()` mostly logs. This is far from the claimed OS-level, memory-patching, hardware-control layer.

Relevant files:

- `backend/asagus/layers/antibot_layer6_native.py`
- `backend/asagus/layers/native/src/browser_patcher.c`
- `backend/asagus/layers/native/src/keyboard_control.cpp`

Impact:

- Layer 6 status can appear enabled even when the actual native capabilities are unavailable.
- Detection resistance claims are not valid.
- Browser memory patching is not actually functional on Linux.

Required fix:

- Separate "configured", "compiled", "loaded", and "actively used" states.
- Remove claims of active patching unless real patch success is verified.
- Add compile/load tests and platform-specific capability checks.

### 7. `require_email` does not enforce email requirement

Severity: High  
Status: Behavioral bug

When `require_email=True` and a record has no email, the pipeline only emits an event note and still stores the partial record.

Relevant file:

- `backend/asagus/main.py`

Impact:

- Jobs can return records that violate their own filter contract.
- Users requesting email-only leads get mixed-quality results.

Required fix:

- If `require_email=True`, skip or mark records without email before storage.
- Add a test for email-required jobs.

### 8. Per-job network enable comments are false

Severity: High  
Status: Behavioral/documentation mismatch

The request model says per-job controls can force a job into real mode, but `effective_runtime_flags()` only enables network/search if the global setting is already enabled.

Relevant files:

- `backend/asagus/models.py`
- `backend/asagus/services/job_helpers.py`

Impact:

- UI/API users may set `enable_network_fetch=True` and still get offline preview behavior.
- Debugging real crawl jobs becomes confusing.

Required fix:

- Either change comments/UI text to "can disable only" or allow per-job explicit enablement with operator authorization.
- Emit a warning event when a requested mode is locked off globally.

## Major Architecture Gaps

### 1. Redis Streams architecture is not implemented

Blueprint expectation:

- Layers communicate through typed Redis Streams.
- Independent workers consume and produce layer events.
- Backpressure and stream lag drive observability.

Actual implementation:

- `run_job()` runs an in-process loop.
- `async_worker.py` and `indexer_worker.py` are placeholders that sleep forever.
- Redis is used only as optional event mirroring when infra persistence is enabled.

Relevant files:

- `backend/asagus/main.py`
- `backend/asagus/workers/async_worker.py`
- `backend/asagus/workers/indexer_worker.py`
- `backend/asagus/services/job_helpers.py`

Impact:

- No true layer isolation.
- No durable work queue.
- No restart-safe in-flight job processing.
- No real stream backpressure handling.

Fix effort:

- Medium to large. Implementing real streams and workers is a multi-week change.

### 2. Persistence does not match production schema

Blueprint expectation:

- Raw HTML in MinIO.
- Structured businesses in PostgreSQL tables.
- Graph relationships in Neo4j.
- Indexing in OpenSearch/Qdrant.

Actual implementation:

- Local JSON/runtime state is primary.
- Optional Postgres mirror writes to a generic `records` table, not the designed `businesses` schema.
- MinIO is best-effort.
- Neo4j only stores simple `Record` nodes during indexing, while graph relationship candidates stay local unless separately handled.

Relevant files:

- `backend/asagus/services/runtime.py`
- `backend/asagus/layers/storage.py`
- `backend/asagus/layers/indexing.py`
- `backend/asagus/db/schema.sql`

Impact:

- Production data model is not actually used.
- Infra failures are swallowed, so operators can believe data is persisted when it is not.
- Cross-service recovery target from the blueprint is not achievable.

Fix effort:

- Medium. Align storage layer with schema and add mandatory/observable persistence modes.

### 3. Self-healing extraction is not true selector repair

Blueprint expectation:

- Scrapling DOM fingerprinting.
- Automatic selector repair.
- Confidence-scored fallback.
- Selector history persisted.

Actual implementation:

- Extraction cascade exists.
- DOM fingerprint stage boosts confidence based on stored hashes.
- Selectors are stored in an in-memory class dictionary as `auto::<field>`.
- No real selector repair, no Scrapling integration, no persistent selector store.

Relevant file:

- `backend/asagus/layers/extraction.py`

Impact:

- The system may appear to "self-heal" by confidence boost, but does not truly learn a new selector.
- Restart loses selector memory.
- Accuracy claims are unsupported.

Fix effort:

- Medium. Real selector repair needs DOM anchoring, selector generation, persistence, and tests with changed DOM fixtures.

### 4. Enrichment is rule-based, not model-backed

Blueprint expectation:

- GLiNER NER.
- spaCy.
- geocoding.
- zero-shot classifier.
- advanced dedup.

Actual implementation:

- Regex/rule phone normalization.
- Simple country inference from phone prefixes.
- Category keyword rules.
- GLiNER availability is only reported, not used directly.
- No geocoding.

Relevant file:

- `backend/asagus/layers/enrichment.py`

Impact:

- Entity quality, geospatial accuracy, and category precision are limited.
- Targets such as "85% valid geocoordinates" cannot be met.

Fix effort:

- Medium. Add optional model adapters and geocoding with cache/rate limits.

### 5. Retrieval is local approximation, not production hybrid search

Blueprint expectation:

- OpenSearch BM25.
- Qdrant HNSW dense vectors.
- MiniLM embeddings.
- Cross-encoder reranking.
- RAG/ReAct query workflow.

Actual implementation:

- Local inverted index and RRF-like fusion.
- Hash/counter vectors and token similarity.
- Several algorithms are marked implemented even where they are local approximations or adapter-ready.

Relevant files:

- `backend/asagus/layers/retrieval.py`
- `backend/asagus/layers/indexing.py`
- `backend/asagus/layers/search_index.py`

Impact:

- Performance and precision claims are not proven.
- Search quality will differ heavily from documented Qdrant/OpenSearch/cross-encoder design.

Fix effort:

- Medium to large, depending on whether model-backed embeddings and real rerankers are required.

## Design Flaws

### Documentation overclaims runtime capability

Several docs describe complete production systems and benchmark-level detection outcomes that the active code does not implement. This is dangerous because it makes project status hard to reason about.

Examples of overclaimed areas:

- "Complete 6-layer anti-detection"
- Camoufox "0% detection"
- CAPTCHA "100% accuracy"
- Redis Streams layer architecture
- 96% extraction accuracy
- Qdrant/OpenSearch/Neo4j production readiness

Recommended fix:

- Split docs into "implemented", "adapter-ready", "planned", and "research reference".
- Add an implementation matrix generated from code or maintained as a single source of truth.

### Safe/compliance behavior conflicts with anti-bot bypass docs

The main pipeline detects challenges and routes them to manual review without bypass. Anti-bot docs describe solving/bypassing challenge systems. This creates a product identity conflict.

Recommended fix:

- Decide and document the product boundary:
  - compliant public-data scraper that avoids challenges, or
  - anti-bot research framework used only in authorized testing.
- Keep the active product path aligned with that boundary.

### Infrastructure errors are swallowed

Postgres, MinIO, OpenSearch, Qdrant, Neo4j, and Redis failures often degrade silently to local-only or `unreachable`.

Recommended fix:

- Add strict mode for production.
- Emit explicit job warnings and health signals when persistence/indexing fails.
- Do not report "stored" or "indexed" without distinguishing local-only from durable infra writes.

### Duplicate logic may merge unrelated leads

Runtime duplicate detection merges on email, phone, WhatsApp, website domain, or social URL. The enrichment layer also assigns high duplicate scores for email domain alone. This can merge separate businesses using the same domain or generic contact address patterns.

Recommended fix:

- Require stronger multi-field evidence for merge.
- Treat shared email domain as a weak signal unless paired with name/address/phone similarity.
- Add review state for ambiguous duplicates.

## Missing Features Against Blueprint

| Blueprint Feature | Current Status | Notes |
| --- | --- | --- |
| Typed Redis Streams between layers | Missing | Workers are placeholders. |
| Durable worker pipeline | Missing | `run_job()` is in-process background work. |
| Camoufox/Patchright/nodriver in active jobs | Missing | Modules/examples exist, not wired into `run_job()`. |
| CAPTCHA solving | Missing/placeholder | Detection exists, real solving not implemented. |
| Native Layer 6 browser patching | Mostly missing | Linux patching returns failure; patch application logs only. |
| Scrapling self-healing selector repair | Missing | Hash/confidence boost only. |
| Persistent selector store | Missing | In-memory class dict. |
| GLiNER/spaCy enrichment | Adapter-ready at best | Rules used in current path. |
| Geocoding | Missing | `lat`/`lng` not populated by enrichment. |
| Advanced dedup with validation | Partial | Simple exact/fuzzy rules. |
| MinIO/Postgres/Neo4j as primary persistence | Partial/optional | Local JSON is primary. |
| OpenSearch/Qdrant production indexing | Partial/optional | Best-effort adapters; hash vectors. |
| Cross-encoder reranking | Missing/local approximation | Token scoring only. |
| RAG/ReAct agent workflow | Partial | Search/summarizer hooks, not full workflow. |
| Prometheus/backpressure observability | Partial | Catalog/state only, no real lag metrics. |
| Benchmark validation for accuracy/performance | Missing | Only compute accelerator tests found. |

## Test Coverage Gaps

Observed test coverage is extremely narrow. The only visible test file targets `ComputeAccelerator`.

Missing critical tests:

- `run_job()` end-to-end behavior with offline mode.
- `run_job()` real-network flag behavior.
- `antibot_preset` selection and fetch strategy wiring.
- `require_email=True` filtering.
- Dynamic fetch strategy selection.
- CAPTCHA detection and solver availability reporting.
- Storage durable/local mode behavior.
- Dedup merge safety.
- Extraction cascade with DOM fixture changes.
- Policy decision and MDP reward behavior.
- Retrieval ranking correctness with fixtures.

## Accuracy Assessment

No reliable accuracy number can be assigned from the current code alone.

Reasons:

- No labeled extraction benchmark.
- No benchmark for selector break recovery.
- No search MRR/precision benchmark.
- No anti-bot detection benchmark.
- No CAPTCHA solver implementation to measure.
- No real geocoding/classification validation.

Current likely accuracy profile:

- Simple static pages with visible email/phone/social links: moderate.
- JavaScript-heavy pages: depends on plain Chromium rendering, likely fragile.
- Google Maps/protected pages: low to unreliable.
- CAPTCHA/challenge-protected pages: not solved by active pipeline.
- Complex entity extraction/geocoding/category accuracy: limited by rules.

## Recommended Fix Roadmap


### Phase 2: Fetch/anti-bot integration

Effort: 1-2 weeks

- Introduce a fetch strategy interface.
- Implement plain HTTP, curl-cffi HTTP, plain browser, and orchestrator browser strategies.
- Use `antibot_preset` to select strategy.
- Add capability reporting for Camoufox/Patchright/nodriver/native.

### Phase 3: Production persistence alignment

Effort: 2-4 weeks

- Make Postgres schema the primary structured store.
- Persist jobs, events, selector fingerprints, and policy feedback.
- Make MinIO archival observable and optionally mandatory.
- Convert local JSON store to development-only.

### Phase 4: Real extraction/enrichment improvements

Effort: 2-4 weeks

- Add DOM fixture tests.
- Implement selector repair or integrate a real DOM fingerprinting library.
- Add persistent selector store.
- Add geocoding and model-backed NER/category adapters.

### Phase 5: Retrieval and benchmark validation

Effort: 2-3 weeks

- Use real embeddings.
- Use Qdrant/OpenSearch in a tested integration path.
- Add MRR/precision benchmark fixtures.
- Add latency targets and regression tests.

### Phase 6: Full architecture hardening

Effort: 4-8+ weeks

- Implement Redis Stream workers.
- Add restart recovery.
- Add stream lag/backpressure metrics.
- Add strict production mode.
- Run soak/failure-injection tests.

## Overall Fix Estimate

| Goal | Estimated Effort |
| --- | ---: |
| Fix critical misleading controls and bugs | 2-4 days |
| Honest real-network MVP | 1-2 weeks |
| Proper anti-bot strategy integration | 1-2 weeks |
| Production persistence and indexing | 2-4 weeks |
| Test suite and benchmarks | 1-2 weeks |
| Full blueprint-level system | 8-12+ weeks |

## Final Verdict

The project has a promising structure and many useful modules, but the implementation is currently much closer to a local-first demo with research adapters than the full ASAGUS 3.0 production blueprint.

The most important engineering move is to stop treating module existence as feature completion. A feature should count as implemented only when it is:

1. wired into the active runtime path,
2. configurable through the public API/UI,
3. observable in job events or health output,
4. covered by tests, and
5. aligned with the documented behavior.

Until those conditions are met, the documentation should call the feature `adapter_ready` or `planned`, not `complete`.

## Implementation Update — 2026-06-03

This report was left intact as the original audit trail. The following fixes were implemented after review, with the project treated as an educational/research scraper rather than a production/commercial system:

| Finding | Current Status |
| --- | --- |
| Bug 1 — `antibot_preset` ignored | Fixed in `backend/asagus/main.py` and `backend/asagus/services/job_helpers.py`. Each job now resolves `high-stealth`, `balanced`, or `high-speed` into the browser/client plan used by `FetchLayer`. |
| Bug 2 — browser path not preset-driven | Partially fixed. The active browser pool now receives the resolved per-job engine: Camoufox preference, Patchright preference, or Playwright. Optional engines still fall back when not installed. |
| Bug 3 — orchestrator not integrated | Partially addressed by wiring the active fetch/browser path to the same preset concept. The full `AntiBotOrchestrator` remains a separate research adapter and is not yet the main job runner. |
| Bug 4 — native config mapping | Corrected by the cross-check as not a real bug; no code change required for that specific claim. |
| Bug 5 — CAPTCHA placeholders | Not implemented. Runtime and docs now avoid claiming CAPTCHA/challenge bypass in the active job path. |
| Bug 6 — Layer 6 aspirational | Not implemented. The new preset plan explicitly sets `native_layer_requested=False` for the active research path. |
| Bug 7 — `require_email` advisory only | Fixed. Records missing email are skipped before enrichment/storage when `require_email=True`. |
| Bug 8 — per-job network enable cannot override global default | Fixed for local educational/research runs. `enable_network_fetch` and `enable_search_discovery` now override backend defaults when explicitly set. |

Additional visibility was added:

- Job events now emit `antibot_preset_resolved` with the selected preset, browser engine, fallback-capability state, and challenge-bypass status.
- `/api/algorithm/state` now includes `browser` and `antibot_presets` state.
- `/api/runtime/mode` now reports per-job controls as `can_override`.
- The frontend run form now sends `antibot_preset`, keeps real fetch/discovery as active per-job switches, and uses "default on/off" wording instead of "locked".

Verification performed:

- `./.venv/bin/python -m pytest tests/test_research_runtime_controls.py` — passed, 5 tests.
- `./.venv/bin/python -m py_compile asagus/main.py asagus/models.py asagus/services/job_helpers.py` — passed.
- `npx tsc --noEmit` in `frontend/` — passed.

Known remaining verification gap:

- Running `./.venv/bin/python -m pytest tests/test_research_runtime_controls.py tests/test_compute_accelerator.py` still fails in `tests/test_compute_accelerator.py` because existing hardware detection takes about 7.7 seconds and mocked accelerator detection returns `cpu`. Those failures predate and are unrelated to the fixes above.
