# ASAGUS Scraper 3.0 Deep Project Audit

Date: 2026-06-02

Scope: full local audit of `asagus-scraper-v3` backend, frontend, dependency manifests, installed dependency state, project organization, tests, and frontend/backend control wiring. No source code was changed for this audit.

## Executive Summary

ASAGUS Scraper 3.0 is a local-first scraping and lead-intelligence console with a FastAPI backend and a Next.js frontend. The core API can import successfully and the frontend production build passes. The project has a strong domain model and a broad set of backend layers, but overall quality is uneven because several large modules centralize too much behavior, some newly added anti-bot modules do not compile, tests are partly scripts rather than isolated pytest tests, and dependency declarations are heavier and less precise than the code currently uses.

Overall rating: **C+ / B- for prototype quality**, **not production-ready yet**.

Most important findings:

- Backend package compilation fails in three anti-bot files.
- Main API import succeeds because those broken modules are not currently imported by `asagus.main`.
- `test_audit.py` passes, but normal `pytest` fails because two test files call `localhost:8000` during test collection.
- Frontend production build passes and controls most backend features, but the UI is concentrated in a single 1,622-line page component.
- Backend route handling is concentrated in a single 1,300-line `main.py`.
- Real scraping controls are correctly gated by backend environment settings, but comments/tooltips imply per-job controls can force real mode even when the backend is locked off.
- Requirements include large production/AI/OCR/infrastructure dependencies, while several are unused in current code or not installed in the local venv.

## Project Architecture

### High-Level Structure

```text
asagus-scraper-v3/
  backend/
    asagus/
      main.py                 FastAPI app, routes, job runner
      models.py               Pydantic API/domain models
      config.py               Settings/env config
      services/               health, streams, runtime state
      layers/                 policy, crawl, discovery, fetch, extraction, enrichment, retrieval, etc.
      llm/                    LLM provider abstraction
      workers/                placeholder async/indexer workers
      db/schema.sql           database schema
    requirements.txt
    requirements-local.txt
    test_audit.py
    test_diag.py
    test_e2e_job.py
  frontend/
    app/page.tsx              whole operator console
    app/globals.css           global styling
    lib/api.ts                typed API client
    package.json
  docker-compose.yml          infra + backend + frontend stack
  docs/
```

### Backend Architecture

The backend uses FastAPI and Pydantic. It exposes routes for setup, health, LLM configuration, jobs, policy, records, observability, graph candidates, intelligence, search, and a job-events WebSocket.

Observed routes:

- `GET /`
- `GET /api/blueprint`
- `GET /api/providers`
- `GET /api/algorithm/state`
- `POST /api/discovery/search`
- `GET /api/health`
- `GET /api/runtime/mode`
- `GET/POST /api/llm/settings`
- `POST /api/llm/test`
- `GET/POST /api/jobs`
- `GET/POST/DELETE /api/jobs/{job_id}`
- `DELETE /api/jobs`
- `POST /api/policy/decision`
- `GET /api/policy/stats`
- `GET /api/policy/domains`
- `GET/DELETE /api/records`
- `DELETE /api/records/{record_id}`
- `DELETE /api/runtime/local-data`
- `GET /api/graph/candidates`
- `GET /api/observability`
- `GET /api/intelligence`
- `POST /api/search`
- `WS /ws/jobs/{job_id}`

The intended architecture is layered:

- Policy: URL routing, skip/defer/crawl decisions.
- Crawl control: seed generation, frontier scheduling, MDP metadata.
- Compliance: robots, allow/block domain checks, pacing.
- Fetch: offline preview, static HTTP, dynamic browser rendering.
- Extraction: CSS/XPath/DOM/heuristic/LLM cascade.
- Enrichment: normalization, validation, dedupe scoring.
- Storage: local runtime storage facade.
- Indexing: placeholder facade for BM25/dense/graph indexing.
- Retrieval/search: local ranking and summaries.
- AI app: LLM summaries and provider-facing behavior.

Strength: the domain concepts are separated clearly in filenames and models.

Weakness: orchestration is centralized in `backend/asagus/main.py`, especially `run_job`, so route registration, job execution, status events, layer construction, cancellation, discovery refill, extraction, storage, and policy feedback are tightly coupled.

### Frontend Architecture

The frontend is a Next.js App Router app with a single-page operator console. It uses:

- `frontend/app/page.tsx`: all tabs, state, forms, job controls, records/search views, helper components.
- `frontend/lib/api.ts`: API wrapper and TypeScript types.
- `frontend/app/globals.css`: global responsive layout and components.

Tabs:

- Setup
- Run
- Algorithms
- Pipeline
- Records
- Search

Strength: the frontend has a real operational workflow and calls most backend APIs.

Weakness: almost all UI logic is in one 1,622-line React component, with 20+ state variables and many unrelated concerns in the same file. This makes future changes risky.

## Code Quality

### Positive Findings

- Pydantic models are used consistently for backend request/response/domain data.
- `Settings` centralizes configuration and uses `pydantic-settings`.
- Runtime state uses an `asyncio.Lock` around shared mutation.
- Frontend TypeScript strict mode is enabled.
- Frontend production build succeeds.
- API client has centralized error handling and token injection.
- Backend has a working focused audit script: `python test_audit.py` passed all 16 sections.
- Real network scraping is locked by backend settings by default, which is safer than allowing the UI to turn it on accidentally.

### Quality Risks

- `backend/asagus/main.py` is 1,300 lines and mixes API registration with core pipeline orchestration.
- `frontend/app/page.tsx` is 1,622 lines and mixes API loading, forms, state, layout, records table, LLM setup, search, and job controls.
- `backend/asagus/models.py` is 581 lines and contains many unrelated model families.
- Several backend layer modules are large: extraction 613 lines, retrieval 629 lines, crawl_control 606 lines, antibot_orchestrator 551 lines, antibot_config 516 lines, discovery 489 lines.
- Broad `except Exception` usage appears across backend services and layers. Some is reasonable for probes/fallbacks, but it can hide real defects.
- Placeholder production workers exist but do no work.
- Docker and requirements imply full production infra, while runtime storage is currently local JSON plus in-memory state.

## Errors And Bugs Found

### 1. Backend Package Compile Fails

Command:

```bash
cd asagus-scraper-v3/backend
./.venv/bin/python -m compileall -q asagus
```

Result: failed.

Files with syntax errors:

- `asagus/layers/antibot_layer4_fingerprinting.py:271`
- `asagus/layers/antibot_layer5_behavior.py:66`
- `asagus/layers/antibot_orchestrator.py:108`

The visible cause is escaped quote syntax such as `f\"...\"` and `\"\"\"` in Python source. Python treats the backslash before the quote as an unexpected line-continuation escape.

Impact:

- The full package cannot compile.
- Any import path that reaches these modules will fail immediately.
- The main API can still import because these modules are currently not imported by `asagus.main`.

Smoke import:

```bash
cd asagus-scraper-v3/backend
./.venv/bin/python -c "import asagus.main; print('main import ok')"
```

Result: `main import ok`.

### 2. Normal Pytest Fails During Collection

Command:

```bash
cd asagus-scraper-v3/backend
./.venv/bin/python -m pytest -q
```

Result: failed with two collection-time errors.

Failing files:

- `test_diag.py`
- `test_e2e_job.py`

Reason: these files make live HTTP requests to `http://localhost:8000` at module import time. If the backend server is not already running, pytest fails before collecting normal tests.

Impact:

- CI cannot run `pytest` cleanly.
- The tests are closer to manual scripts than pytest tests.
- Failures are environmental and happen before fixtures can start/skip services.

Positive note: `python test_audit.py` passed.

### 3. Per-Job Real Mode Documentation Mismatch

In `backend/asagus/models.py`, comments say per-job overrides can force real or preview mode. In actual code, `effective_runtime_flags` only allows per-job settings to disable globally enabled modes; they cannot enable real network fetch/search discovery if backend settings are false.

Actual behavior:

```python
return (
    settings.enable_network_fetch and request.enable_network_fetch is not False,
    settings.enable_search_discovery and request.enable_search_discovery is not False,
)
```

Frontend checkboxes are disabled when backend mode is locked, which matches actual behavior. But the UI tooltip says real fetch/discovery needs env OR per-job, which is misleading because per-job cannot override a locked backend.

Impact:

- Users may think the frontend checkbox can enable real scraping without env changes.
- Backend behavior is safer, but docs/tooltips should match it.

### 4. Production Worker Services Are Placeholders

`backend/asagus/workers/async_worker.py` and `backend/asagus/workers/indexer_worker.py` loop forever and sleep. Docker Compose starts them as services, but they do not consume Redis Streams or index data.

Impact:

- Compose suggests a distributed worker architecture that is not implemented.
- Operational users may assume background workers perform indexing/fetching.

### 5. Indexing Layer Is A Facade, Not Real Indexing

`backend/asagus/layers/indexing.py` returns queued statuses for BM25, dense, and graph, but does not write to OpenSearch, Qdrant, or Neo4j.

Impact:

- Local search works through runtime records/retrieval, but production index dependencies are not actually used by this layer yet.
- Docker services and requirements are ahead of implemented behavior.

### 6. Frontend Error Display Truncates Useful Details

The topbar displays `error.slice(0, 100)`. For backend validation or connection failures, this can hide the actionable part of the message.

Impact:

- User friendliness suffers when debugging failed jobs or LLM settings.

### 7. Local Runtime Persistence Is Useful But Not Production-Grade

`RuntimeState` stores jobs/events/records in local JSON files under `data/`. It is good for local development, but the comment itself says production should use Postgres + Redis Streams.

Impact:

- Multi-process deployments can diverge.
- Large datasets will stress JSON file persistence.
- Docker Compose includes Postgres/Redis, but the main job state path is local runtime storage.

## Dependency Audit

### Backend Requirements Declared

`backend/requirements.txt` declares:

- Web/API: `fastapi`, `uvicorn[standard]`, `pydantic`, `pydantic-settings`, `python-dotenv`
- HTTP/search/scraping: `httpx[http2]`, `ddgs`, `selectolax`, `lxml`, `trafilatura`, `playwright`, `scrapling`, `crawl4ai`
- Data validation/enrichment: `phonenumbers`, `geopy`, `dnspython`, `rapidfuzz`
- Infra clients: `redis`, `asyncpg`, `qdrant-client`, `opensearch-py`, `neo4j`, `boto3`, `prometheus-client`
- Retrieval/AI/OCR/acceleration: `rank-bm25`, `sentence-transformers`, `torch`, `easyocr`, `paddleocr`, `openvino`
- Anti-bot: `curl-cffi`

`backend/requirements-local.txt` declares a smaller local set:

- `fastapi`, `uvicorn[standard]`, `pydantic`, `pydantic-settings`, `httpx[http2]`, `python-dotenv`, `ddgs`, `selectolax`, `lxml`, `playwright`, `dnspython`, `pytest`

### Backend Installed In Local Venv

The backend venv exists at `backend/.venv` and uses Python 3.13. Installed top-level highlights:

- API: `fastapi==0.136.3`, `uvicorn==0.48.0`, `pydantic==2.13.4`, `pydantic-settings==2.14.1`
- HTTP/search/scraping: `httpx==0.28.1`, `ddgs==9.14.4`, `selectolax==0.4.10`, `lxml==5.4.0`, `trafilatura==2.0.0`, `playwright==1.60.0`, `scrapling==0.2.99`, `Crawl4AI==0.8.7`
- Infra: `redis==8.0.0`, `asyncpg==0.31.0`, `qdrant-client==1.18.0`, `opensearch-py==3.2.0`, `neo4j==6.2.0`, `boto3==1.43.19`, `prometheus_client==0.25.0`
- AI/retrieval: `rank-bm25==0.2.2`, `sentence-transformers==5.5.1`, `torch==2.12.0`, `transformers==5.9.0`, `openai==2.40.0`
- Anti-bot/browser-related installed transitively or directly: `camoufox==0.4.11`, `patchright==1.60.0`, `playwright-stealth==2.0.3`, `rebrowser_playwright==1.52.0`
- Utility/transitive: `PyYAML==6.0.3`, `numpy==2.4.6`, `scikit-learn==1.8.0`, `scipy==1.17.1`

Declared but not found by `pip show` in local venv:

- `easyocr`
- `paddleocr`
- `openvino`
- `curl-cffi`

Installed but not declared directly in `requirements.txt` and relevant to source/developer intent:

- `PyYAML` is imported in `antibot_config.py`, but only installed transitively.
- `openai` is installed, but not directly declared.
- `camoufox`, `patchright`, `playwright-stealth`, and `rebrowser_playwright` are installed, but mostly via scraping dependencies/transitives and comments rather than direct requirements.
- `numpy` is installed transitively and comments mention optional trajectory generation.

### Backend Code Imports Observed

External imports used directly in source include:

- `fastapi`
- `pydantic`
- `pydantic_settings`
- `httpx`
- `asyncpg`
- `redis.asyncio`
- `playwright.async_api`
- `yaml`

Many declared dependencies are not directly imported by current source, or are only represented as future adapters/placeholders: Qdrant, OpenSearch, Neo4j, Boto3, Prometheus client, sentence-transformers, Torch, OCR packages.

### Frontend Declared Dependencies

`frontend/package.json` declares:

- Runtime: `next`, `react`, `react-dom`, `lucide-react`
- Dev: `typescript`, `@types/node`, `@types/react`, `@types/react-dom`

### Frontend Installed Dependencies

`npm ls --depth=0` shows:

- `next@15.5.18`
- `react@19.2.6`
- `react-dom@19.2.6`
- `lucide-react@0.475.0`
- `typescript@5.9.3`
- `@types/node@22.19.19`
- `@types/react@19.2.15`
- `@types/react-dom@19.2.3`

The installed versions satisfy the semver ranges declared in `package.json`.

## Frontend Analysis

### User Friendliness

Good:

- The UI is an actual operator console, not a landing page.
- Navigation is clear through six tabs.
- Health, real/preview mode, LLM readiness, jobs, and record count are visible globally.
- Forms expose advanced scraping controls: mode, discovery mode, lead target, proxy strategy, domain filters, resource profile, browser/action limits, evidence capture, robots, skip-existing, contact/social followups, and require-email.
- Destructive actions use confirmation dialogs.
- The layout has responsive media queries for tablet/mobile.
- Tables have horizontal overflow handling.
- The app uses icons from `lucide-react`.

Weak:

- The Run form exposes many controls at once, which is powerful but cognitively heavy for non-technical users.
- Error display is truncated in the top bar.
- There is no visible step-by-step validation or preview of what the job will do before submitting.
- All job polling uses 5-second interval HTTP refresh; the backend WebSocket exists, but the frontend does not use it.
- The selected job can be overwritten by refresh behavior when `selectedJobIdRef` is empty, which is acceptable but can feel jumpy when many jobs exist.
- The LLM snippet parser is convenient, but regex parsing of pasted code is inherently fragile.

### Frontend Controls vs Backend

Controls that are wired to backend:

- Operator token -> Authorization header.
- LLM provider/model/API key/base URL/temperature/timeout/concurrency -> `/api/llm/settings`.
- LLM test -> `/api/llm/test`.
- Job start -> `/api/jobs`.
- Job cancel/delete/clear -> job endpoints.
- Record delete/clear -> records endpoints.
- Clear all local data -> `/api/runtime/local-data`.
- Search -> `/api/search`.
- Algorithm/observability/graph views -> `/api/algorithm/state`, `/api/observability`, `/api/graph/candidates`.
- Health/runtime mode -> `/api/health`, `/api/runtime/mode`.

Missing or underused backend controls:

- Backend WebSocket `/ws/jobs/{job_id}` is not used by frontend.
- `/api/discovery/search` is not directly exposed as a separate discovery preview tool.
- `/api/policy/decision` is not exposed as a URL decision tester.
- `/api/policy/domains` is not shown directly, though policy stats and algorithm state are visible.
- `/api/intelligence` is not directly exposed, though some related algorithm/intelligence summaries appear elsewhere.

Conclusion: the frontend controls the main backend workflows properly, but it does not use every backend capability and does not use the real-time WebSocket path.

## Verification Results

Commands run:

```bash
cd asagus-scraper-v3/backend
./.venv/bin/python -m compileall -q asagus
```

Result: failed due syntax errors in three anti-bot modules.

```bash
cd asagus-scraper-v3/backend
./.venv/bin/python -c "import asagus.main; print('main import ok')"
```

Result: passed.

```bash
cd asagus-scraper-v3/backend
./.venv/bin/python -m pytest -q
```

Result: failed during collection because `test_diag.py` and `test_e2e_job.py` call `localhost:8000` at import time.

```bash
cd asagus-scraper-v3/backend
./.venv/bin/python test_audit.py
```

Result: passed all 16 audit sections.

```bash
cd asagus-scraper-v3/frontend
npm run build
```

Result: passed.

Build output summary:

- `/` route built as static content.
- First Load JS: 116 kB.
- Shared JS: 102 kB.

```bash
cd asagus-scraper-v3/frontend
npm ls --depth=0
```

Result: installed frontend packages satisfy declared dependency ranges.

```bash
cd asagus-scraper-v3/backend
./.venv/bin/python -m pip freeze
```

Result: backend venv has many declared and transitive packages installed, but several heavy declared packages are absent.

## Recommendations

Priority 1:

- Fix syntax errors in the three anti-bot modules.
- Convert `test_diag.py` and `test_e2e_job.py` into real pytest tests or rename them as manual scripts so `pytest` can run cleanly.
- Update comments/tooltips around per-job real scraping controls to say backend env gates are authoritative.

Priority 2:

- Split `main.py` into route modules and a pipeline/job service.
- Split `page.tsx` into tab components and reusable form/table/progress components.
- Decide whether workers/indexing are placeholders or production features; either implement them or mark them clearly as future adapters.
- Make dependency declarations match actual code: direct dependencies for imported modules, optional extras for OCR/AI/anti-bot/prod infra.

Priority 3:

- Use the existing WebSocket endpoint for live job events instead of polling only.
- Improve error display so full backend messages can be expanded.
- Add a discovery preview/policy decision tester to expose currently unused backend endpoints.
- Add isolated unit tests for runtime storage, fetch modes, extraction, API validation, and frontend API payload generation.
- Add lockfiles or constraints for backend dependencies to prevent very large dependency drift.

## Final Assessment

The project is ambitious and already has a usable local operator console. The strongest parts are the domain model, local runtime usability, frontend/backend API coverage, and the focused audit script. The biggest blockers are compile-breaking anti-bot modules, test files that fail under normal pytest, and a gap between production-looking infrastructure and currently local/placeholder implementations.

The next best engineering step is not a broad rewrite. It is to stabilize the basics: make the package compile, make pytest clean, clarify the real/preview mode contract, then modularize `main.py` and `page.tsx` once behavior is stable.
