# ASAGUS Scraper 3.0 Deep Audit Report

Date: 2026-06-02

Scope:
- Full non-vendor code review across backend, frontend, scripts, Docker, compose, and infra files.
- Backend and frontend server restart.
- `pytest` installation into the backend virtual environment.
- Backend compile, pytest collection, project audit test, frontend production build, health/API checks, and target-5 mode matrix.
- Dependency/import audit against `backend/requirements.txt`.

Important boundary:
- No application source code was changed during this report pass.
- `pytest` was installed into `backend/.venv`.
- This report file was added under `docs/`.
- Existing dirty worktree changes were preserved.

## Executive Summary

ASAGUS Scraper 3.0 is a strong local prototype with a usable FastAPI control plane, Next.js operator console, local file-backed runtime state, policy/crawl/extract/enrich/search layers, and guarded preview behavior. The app starts, the frontend builds, and the live API can execute target-5 offline jobs across all main modes and discovery submodes.

The largest problems are not syntax or basic startup. The largest problems are consistency, test harness quality, local setup drift, production-readiness gaps, and several modules that are described as production systems but currently behave as local adapters/placeholders.

Current overall rating: 6.8 / 10

## Verification Summary

| Check | Result | Notes |
| --- | --- | --- |
| Backend Python compile | PASS | `python -m py_compile` passed for all backend modules. |
| `pytest` installed | PASS | Installed `pytest 9.0.3` into `backend/.venv`. |
| `pytest -q` | FAIL | `test_audit.py` executes at import time and calls `sys.exit(1)`, causing pytest internal collection failure. |
| `python test_audit.py` | FAIL | Fails on `comprehensive` mode planning expectation. |
| Frontend production build | PASS | `npm run build` completed successfully. |
| Backend restart | PASS | Uvicorn restarted on `http://127.0.0.1:8000`. |
| Frontend restart | PASS | Next dev server restarted on `http://127.0.0.1:3000`. |
| Health endpoint | PASS | `/api/health` returned `status=ok`. Optional stores were unreachable but marked optional in local mode. |
| Target-5 mode matrix | MIXED | Script reported 12 passed, 6 HTTP client timeouts; backend records show all 18 matrix jobs eventually completed. |

## Code Files Reviewed

Backend core:
- `backend/asagus/config.py`
- `backend/asagus/models.py`
- `backend/asagus/main.py`
- `backend/asagus/services/runtime.py`
- `backend/asagus/services/health.py`
- `backend/asagus/services/streams.py`
- `backend/asagus/llm/providers.py`

Backend layers:
- `backend/asagus/layers/policy.py`
- `backend/asagus/layers/crawl_control.py`
- `backend/asagus/layers/compliance.py`
- `backend/asagus/layers/fetch.py`
- `backend/asagus/layers/discovery.py`
- `backend/asagus/layers/extraction.py`
- `backend/asagus/layers/enrichment.py`
- `backend/asagus/layers/storage.py`
- `backend/asagus/layers/indexing.py`
- `backend/asagus/layers/retrieval.py`
- `backend/asagus/layers/search_index.py`
- `backend/asagus/layers/browser.py`
- `backend/asagus/layers/browser_actions.py`
- `backend/asagus/layers/challenge_detector.py`
- `backend/asagus/layers/compute_accelerator.py`
- `backend/asagus/layers/dom_tools.py`
- `backend/asagus/layers/fingerprint_advanced.py`
- `backend/asagus/layers/human_behavior.py`
- `backend/asagus/layers/mode_control.py`
- `backend/asagus/layers/resource_governor.py`
- `backend/asagus/layers/proxy.py`
- `backend/asagus/layers/graph.py`
- `backend/asagus/layers/geoint.py`
- `backend/asagus/layers/analytics.py`
- `backend/asagus/layers/nlp_intelligence.py`
- `backend/asagus/layers/observability.py`
- `backend/asagus/layers/osint.py`
- `backend/asagus/layers/vision.py`
- `backend/asagus/layers/throughput.py`

Backend scripts/workers/tests:
- `backend/asagus/scripts/init_db.py`
- `backend/asagus/scripts/init_qdrant.py`
- `backend/asagus/workers/async_worker.py`
- `backend/asagus/workers/indexer_worker.py`
- `backend/test_audit.py`
- `backend/test_diag.py`
- `backend/test_e2e_job.py`
- `backend/audit_mode_matrix.py`

Frontend:
- `frontend/app/layout.tsx`
- `frontend/app/page.tsx`
- `frontend/app/globals.css`
- `frontend/lib/api.ts`
- `frontend/next.config.ts`
- `frontend/tsconfig.json`
- `frontend/package.json`
- `frontend/Dockerfile`

Project/infra:
- `backend/Dockerfile`
- `docker-compose.yml`
- `infra/prometheus.yml`
- `run-backend-linux.sh`
- `run-frontend-linux.sh`
- `run.txt`

Generated runtime JSON and raw HTML archives were not treated as code.

## Test Details

### Backend Compile

Command:

```bash
find backend/asagus -type f -name '*.py' -not -path '*/__pycache__/*' -print0 | xargs -0 -n1 python3 -m py_compile
```

Result:

```text
py_compile_ok
```

### Pytest

Command:

```bash
cd backend
.venv/bin/python -m pytest -q
```

Result:

```text
INTERNALERROR ... SystemExit: 1
no tests ran
```

Cause:
- `backend/test_audit.py` runs `asyncio.run(main())` at module import time.
- Pytest imports test modules during collection.
- The script fails and calls `sys.exit(1)`, so pytest fails during collection instead of running tests normally.

### Project Audit Script

Command:

```bash
cd backend
.venv/bin/python test_audit.py
```

Result:

```text
FAIL mode=comprehensive limit=50 -> planned=300 >= 1500
```

Cause:
- `ScrapeStartRequest.mode` allows `comprehensive`, but `planned_page_count()` does not define a `comprehensive` multiplier.
- It falls back to multiplier `6`.
- Test expects at least `1500` planned pages for `limit=50`.

### Frontend Build

Command:

```bash
cd frontend
npm run build
```

Result:

```text
Compiled successfully
Route (app) Size First Load JS
/ 13.4 kB 116 kB
```

### Server Restart

Ports were cleared with:

```bash
fuser -k 8000/tcp 3000/tcp
```

Restarted:

```bash
cd backend
.venv/bin/python -m uvicorn asagus.main:app --host 127.0.0.1 --port 8000
```

```bash
cd frontend
npm run dev -- --hostname 127.0.0.1 --port 3000
```

Confirmed:
- Backend: `http://127.0.0.1:8000`
- Frontend: `http://127.0.0.1:3000`

### Health and Runtime Mode

`/api/health` returned:

```json
{
  "status": "ok",
  "services": {
    "postgres": "optional_unreachable",
    "redis": "optional_unreachable",
    "opensearch": "optional_unreachable",
    "qdrant": "optional_unreachable",
    "minio": "optional_unreachable",
    "neo4j": "optional",
    "network_fetch": "enabled",
    "search_discovery": "enabled"
  }
}
```

Important:
- The running environment has real fetch and real discovery enabled globally.
- The target-5 mode matrix forced both `enable_network_fetch=false` and `enable_search_discovery=false` per job.

### Target-5 Mode Matrix

Script:

```bash
cd backend
.venv/bin/python audit_mode_matrix.py
```

Script output:

```text
12 passed, 6 failed
```

Reported failures:
- `fast / website_first`
- `fast / social_first`
- `fast / social_only`
- `balanced / website_first`
- `balanced / social_first`
- `balanced / social_only`

Observed backend state after the run:
- All 18 matrix jobs eventually reached `completed`.
- Each processed `5`.
- Each skipped `5`.
- Each stored `0` records.

Interpretation:
- Functional job completion succeeded for all 18 mode/submode combinations.
- The matrix script still failed 6 cases because its HTTP request timeout was too tight for the backend response behavior under sequential background jobs.
- This is an API/test-harness responsiveness issue and should be fixed.

## Dependency Audit

Third-party imports detected in backend code:

```text
asyncpg
ddgs
dns
easyocr
fastapi
httpx
lxml
openvino
paddleocr
playwright
pydantic
pydantic_settings
redis
selectolax
sentence_transformers
torch
```

Current local installed status:

```text
pytest: installed
torch: installed
easyocr: MISSING
paddleocr: MISSING
openvino: MISSING
fastapi: installed
uvicorn: installed
ddgs: installed
playwright: installed
pip check: No broken requirements found.
```

Dependency finding:
- `torch`, `easyocr`, `paddleocr`, and `openvino` are listed in `backend/requirements.txt`.
- `easyocr`, `paddleocr`, and `openvino` are not installed in the current backend venv.
- The current code catches `ImportError` in optional paths, so basic startup still works.
- A clean `pip install -r backend/requirements.txt` may be heavy and may fail or take a long time on Python 3.13 because OCR/ML packages are large and version compatibility can vary.

## Issues

### 1. `test_audit.py` Fails Because `comprehensive` Mode Has No Multiplier

Severity: High

Files:
- `backend/asagus/models.py`
- `backend/asagus/main.py`
- `backend/test_audit.py`

Evidence:
- `ScrapeStartRequest.mode` allows `focused`, `comprehensive`, and `adaptive`.
- `planned_page_count()` only handles `fast`, `balanced`, `deep`, `deep_agent`, `parallel`, and `research`.
- `mode_plan()` has the same missing multiplier map.
- `test_audit.py` expects:
  - `focused`: at least `200`
  - `comprehensive`: at least `1500`
  - `adaptive`: at least `400`

Line references:
- `backend/asagus/models.py:231`
- `backend/asagus/main.py:1014`
- `backend/asagus/main.py:1055`
- `backend/test_audit.py:40`

Impact:
- Existing audit test cannot pass.
- UI and API semantics are inconsistent for modes that are accepted by the model but not described in runtime mode output.
- Operators may select or send valid API modes that silently behave like `balanced`.

Recommendation:
- Either remove `focused`, `comprehensive`, and `adaptive` from `ScrapeStartRequest.mode`, or add explicit planning behavior for all three in `planned_page_count()`, `mode_plan()`, frontend controls, and `/api/runtime/mode`.

### 2. Pytest Collection Is Broken By Script-Style Tests

Severity: High

File:
- `backend/test_audit.py`

Evidence:
- Pytest imports `test_audit.py`.
- The file runs `asyncio.run(main())` at top level.
- Failures call `sys.exit(1)`.

Impact:
- `pytest -q` cannot be used reliably.
- CI would fail during collection instead of giving normal test reports.
- Test output is hard to compose with other tests.

Recommendation:
- Wrap script execution in:

```python
if __name__ == "__main__":
    asyncio.run(main())
```

- Convert checks into pytest functions with assertions.
- Add `pytest.mark.asyncio` or use `anyio`/`pytest-asyncio` if async tests remain.

### 3. Linux Run Script References Missing Files

Severity: High

File:
- `run-backend-linux.sh`

Evidence:
- `run-backend-linux.sh` copies `.env.example`.
- Root `.env.example` is missing in the current worktree.
- It installs `backend/requirements-local.txt`.
- `backend/requirements-local.txt` is missing.

Line references:
- `run-backend-linux.sh:6`
- `run-backend-linux.sh:18`

Impact:
- Fresh Linux no-Docker startup fails.
- README promises this script works, but the required files are absent.

Recommendation:
- Restore `.env.example`.
- Add `backend/requirements-local.txt` or update the script to install `backend/requirements.txt`.
- Keep README and run scripts aligned.

### 4. README Documents Missing `requirements-local.txt`

Severity: Medium

File:
- `README.md`

Evidence:
- README says the Linux script installs lightweight local dependencies from `backend/requirements-local.txt`.
- That file is missing.

Impact:
- First-run user instructions are misleading.

Recommendation:
- Either add the file or remove the claim and explain the full requirements install.

### 5. Target-5 Matrix Exposes API/Test Responsiveness Issue

Severity: Medium

File:
- `backend/audit_mode_matrix.py`
- `backend/asagus/main.py`
- `backend/asagus/services/runtime.py`

Evidence:
- Matrix script reported 6 HTTP timeouts.
- Backend state later showed all 18 jobs completed.
- Jobs are run as FastAPI background tasks using the local in-process runtime.
- Runtime writes JSON state/events frequently under an async lock.

Impact:
- Tests can fail even when jobs complete.
- UI polling can feel slow or unreliable under repeated local jobs.
- This may become worse with larger jobs because each event update persists JSON to disk.

Recommendation:
- Increase test script HTTP timeout and print progress with `flush=True`.
- Reduce per-event synchronous JSON persistence or batch writes.
- Move job execution to a proper worker/queue path for production.
- Add an API endpoint to wait for job completion with a server-side timeout.

### 6. Production Queue/Worker Architecture Is Mostly Placeholder

Severity: Medium-High

Files:
- `backend/asagus/services/streams.py`
- `backend/asagus/workers/async_worker.py`
- `backend/asagus/workers/indexer_worker.py`
- `backend/asagus/services/runtime.py`

Evidence:
- `StreamBus` defaults to `enabled=False` and returns `local-noop`.
- `async_worker.py` sleeps forever.
- `indexer_worker.py` sleeps forever.
- Runtime docstring explicitly says production should use Postgres + Redis Streams, but local file state is used.

Line references:
- `backend/asagus/services/streams.py:16`
- `backend/asagus/workers/async_worker.py:6`
- `backend/asagus/workers/indexer_worker.py:6`
- `backend/asagus/services/runtime.py:27`

Impact:
- Docker compose starts workers that do not process real jobs.
- Architecture docs promise Redis Streams, but the actual system runs in-process via the API.
- Scalability and backpressure are not production-ready.

Recommendation:
- Implement Redis Stream consumers.
- Move `run_job()` execution out of FastAPI background tasks into workers.
- Persist jobs/records/events in Postgres for production.
- Use Redis only for queue/state coordination, not as a replacement for durable records.

### 7. Production Storage/Indexing Integrations Are Mostly Adapter Contracts

Severity: Medium

Files:
- `backend/asagus/layers/storage.py`
- `backend/asagus/layers/indexing.py`
- `backend/asagus/layers/retrieval.py`
- `backend/asagus/layers/search_index.py`
- `backend/asagus/layers/graph.py`

Evidence:
- Storage is local runtime/file archive oriented.
- Indexing layer reports queued/adapter behavior rather than writing OpenSearch/Qdrant/Neo4j.
- Retrieval uses local inverted index/hash-vector approximations.
- Graph produces relationship candidates but does not materialize Neo4j edges.

Impact:
- The local demo works.
- The documented production stack is not fully implemented.
- Search claims should be described as local approximations unless external store adapters are wired.

Recommendation:
- Add concrete repository/index clients for Postgres, Qdrant, OpenSearch, Neo4j, and MinIO.
- Add integration tests behind Docker compose.
- Make `/api/algorithm/state` label adapter-ready features clearly.

### 8. Real Fetch/Discovery Enabled In Current Environment

Severity: Medium

Files:
- `.env`
- `backend/asagus/config.py`
- `backend/asagus/main.py`

Evidence:
- `/api/runtime/mode` reports `network_fetch_enabled=true` and `search_discovery_enabled=true`.
- Health reports both as enabled.
- The matrix test had to explicitly force both flags false per job.

Impact:
- `test_e2e_job.py` and UI jobs may perform real scraping/discovery unless the operator disables it.
- This is different from the README's stated local safety default.

Recommendation:
- Ensure `.env.example` defaults to:

```dotenv
ENABLE_NETWORK_FETCH=false
ENABLE_SEARCH_DISCOVERY=false
```

- Consider a prominent backend startup log warning when real mode is enabled.
- Make test scripts explicitly disable real fetch/discovery unless they are intentionally integration tests.

### 9. `test_e2e_job.py` Can Trigger Real Network Jobs

Severity: Medium

File:
- `backend/test_e2e_job.py`

Evidence:
- Payload does not set `enable_network_fetch=false`.
- Payload does not set `enable_search_discovery=false`.
- Current backend environment has both globally enabled.

Impact:
- Running the script may make real web requests.
- Results depend on external networks/search engines.

Recommendation:
- Add explicit offline flags for safe test mode.
- Create separate `test_e2e_real.py` requiring an environment opt-in.

### 10. Mutable Defaults In Pydantic Browser Action Models

Severity: Medium

File:
- `backend/asagus/layers/browser_actions.py`

Evidence:
- `BrowserAction.metadata` defaults to `{}`.
- `BrowserActionResult.metadata` defaults to `{}`.

Line reference:
- `backend/asagus/layers/browser_actions.py:52`

Impact:
- Pydantic v2 often copies mutable defaults, but using mutable literal defaults is still a code-quality 

Recommendation:
- Use `Field(default_factory=dict)`.

### 11. Browser Action Selectors Are Not Validated Before Playwright Calls

Severity: Medium

File:
- `backend/asagus/layers/browser_actions.py`

Evidence:
- `click`, `fill`, `type`, `select`, `wait_for_selector`, `extract_text`, and other actions call Playwright with `action.selector`, which may be `None`.

Line references:
- `backend/asagus/layers/browser_actions.py:104`
- `backend/asagus/layers/browser_actions.py:110`
- `backend/asagus/layers/browser_actions.py:114`
- `backend/asagus/layers/browser_actions.py:129`
- `backend/asagus/layers/browser_actions.py:140`

Impact:
- Invalid workflow actions can fail late and unclearly.
- A deep-agent workflow can waste action budget on malformed actions.

Recommendation:
- Validate required fields per action type before execution.
- Return structured validation errors.

### 12. Resource Governor Metrics Can Divide By Zero

Severity: Medium

File:
- `backend/asagus/layers/resource_governor.py`

Evidence:
- `browser_utilization` divides by `self.browser_pool_size`.
- Constructor allows caller to pass `browser_pool_size=0`.

Line reference:
- `backend/asagus/layers/resource_governor.py:76`

Impact:
- `get_metrics()` can raise `ZeroDivisionError`.

Recommendation:
- Clamp to at least 1 or use `max(value, 1)` in denominators.

### 13. Resource Governor Queue Counters Measure Active Tasks, Not Queued Work

Severity: Low-Medium

File:
- `backend/asagus/layers/resource_governor.py`

Evidence:
- Counters increment only after acquiring semaphores.
- Work waiting on semaphores is not counted.

Line references:
- `backend/asagus/layers/resource_governor.py:32`
- `backend/asagus/layers/resource_governor.py:41`
- `backend/asagus/layers/resource_governor.py:50`

Impact:
- `can_accept_work()` does not reflect actual pending pressure.
- Metrics under-report backlog.

Recommendation:
- Track waiting counts before semaphore acquisition and active counts after acquisition.

### 14. Compliance Layer Always Applies Unknown-Domain Delay Even When Token Is Available

Severity: Low-Medium

File:
- `backend/asagus/layers/compliance.py`

Evidence:
- Delay is calculated as the max of robots delay, token wait, and default unknown-domain delay.
- Even when token is available, delay is at least `default_unknown_domain_delay_seconds`.
- In offline mode, delay is not slept because `effective_network_fetch` is false.

Line references:
- `backend/asagus/layers/compliance.py:143`
- `backend/asagus/layers/compliance.py:145`

Impact:
- Real network jobs wait for every domain even after token approval.
- This is safe but may reduce throughput more than expected.

Recommendation:
- Separate required pre-fetch delay from informational default delay.
- Only sleep when robots/token bucket actually requires it, or make the conservative delay explicit in docs.

### 15. Local Runtime Persists Events Frequently And Can Become Large

Severity: Medium

Files:
- `backend/asagus/services/runtime.py`
- `data/runtime_events.json`

Evidence:
- Every event persists the entire events payload.
- Runtime event file is large in the current workspace.
- Matrix test responsiveness showed client timeouts while jobs still completed.

Line references:
- `backend/asagus/services/runtime.py:81`
- `backend/asagus/services/runtime.py:410`

Impact:
- Local app slows over time.
- API background tasks may compete with polling and test requests.

Recommendation:
- Store only append-only event logs or persist per-job files.
- Compact old events.
- Add maintenance endpoint or CLI cleanup.

### 16. Health Says Optional Stores Are OK For Local, But Production State Is Not Enforced

Severity: Medium

File:
- `backend/asagus/services/health.py`

Evidence:
- Local unreachable services are marked `optional_unreachable`.
- This is fine locally, but no production guard is visible that fails startup when required stores are unreachable.

Line references:
- `backend/asagus/services/health.py:17`
- `backend/asagus/services/health.py:66`

Impact:
- Production deployments can appear superficially healthy if environment is misclassified.

Recommendation:
- In production, fail health if Postgres/Redis/index stores are unavailable.
- Add `/api/health/ready` and `/api/health/live` with different strictness.

### 17. Frontend Uses A Very Large Single Page Component

Severity: Medium

File:
- `frontend/app/page.tsx`

Evidence:
- File is about 1,619 lines.
- It handles setup, run form, algorithms, pipeline, records, search, local token, provider import parsing, and rendering.

Impact:
- Hard to test.
- Hard to review.
- Higher risk of accidental UI regressions.

Recommendation:
- Split into tabs/components:
  - `SetupTab`
  - `RunTab`
  - `PipelineTab`
  - `RecordsTab`
  - `SearchTab`
  - `AlgorithmsTab`
  - API hooks/state helpers

### 18. Frontend Lint Script Is Probably Invalid For Next 15

Severity: Low-Medium

File:
- `frontend/package.json`

Evidence:
- Script is `"lint": "next lint"`.
- Recent Next versions have changed lint behavior and often require ESLint setup directly.

Impact:
- `npm run lint` may fail or be unavailable depending on Next CLI behavior.

Recommendation:
- Add explicit ESLint dependencies/config or remove/replace the lint script with a known working command.

### 19. Docker Compose Workers Do Not Provide Claimed Pipeline Processing

Severity: Medium

Files:
- `docker-compose.yml`
- `backend/asagus/workers/async_worker.py`
- `backend/asagus/workers/indexer_worker.py`

Evidence:
- Compose starts `async-worker` and `indexer-worker`.
- Worker files sleep forever.

Impact:
- Docker deployment looks more complete than it is.
- Operators may expect distributed processing that is not implemented.

Recommendation:
- Mark worker services as placeholders or implement consumers before calling compose production-ready.

### 20. Docker Build May Be Heavy Or Fragile Due to Full ML/OCR Requirements

Severity: Medium

File:
- `backend/Dockerfile`
- `backend/requirements.txt`

Evidence:
- Docker installs all backend requirements.
- Requirements include large ML/OCR packages.
- Docker image is Python 3.12, local venv is Python 3.13.

Impact:
- Local and Docker dependency behavior can diverge.
- Full Docker build may be slow or fail depending package wheels.

Recommendation:
- Split requirements:
  - `requirements-base.txt`
  - `requirements-ml.txt`
  - `requirements-prod.txt`
  - `requirements-dev.txt`
- Install optional OCR/ML extras only when enabled.

## Architecture Assessment

### What Works Well

- FastAPI route structure is broad and usable.
- Next.js frontend builds and gives an operator-friendly console.
- Backend safety gates exist: global environment flags plus per-job disable-only controls.
- Offline preview mode prevents demo data from being stored as leads.
- Policy, crawl scheduler, extraction cascade, enrichment, graph candidates, and retrieval all have working local implementations.
- LLM provider registry is flexible and supports many provider styles.

- Raw HTML archive and local runtime persistence make local debugging possible.

### What Is Partly Implemented

- MDP scheduler is a real local scoring/scheduling system, but not trained from durable production history yet.
- Hybrid retrieval is locally implemented with deterministic approximations, not real OpenSearch/Qdrant neural infrastructure.
- Graph logic creates candidates, not Neo4j graph materialization.
- Redis Streams facade exists, but worker processing is not implemented.
- Browser action DSL exists, but it is not wired into the main `run_job()` deep-agent execution path.
- Compute accelerator detects optional packages, but OCR/GPU dependencies are not installed locally.

### What Is Mostly Documentation/Adapter

- Production Redis Streams pipeline.
- Production Postgres repositories.
- Production OpenSearch/Qdrant indexing.
- Production Neo4j graph writes.
- MinIO raw archive integration.
- Dedicated worker scaling.
- Full deep-agent browser workflows.

## Code Quality Ratings

| Area | Rating | Reason |
| --- | ---: | --- |
| Backend startup | 8/10 | Starts and compiles cleanly. |
| Backend testability | 4/10 | Script-style tests break pytest; audit test fails. |
| API design | 7/10 | Broad useful endpoints, but long `main.py` and local state coupling. |
| Runtime persistence | 5/10 | Useful locally, but JSON/event persistence will not scale. |
| Policy/crawl logic | 7/10 | Good local model; mode inconsistency needs fixing. |
| Extraction/enrichment | 7/10 | Practical fallback cascade; still mostly regex/heuristic. |
| Retrieval/search | 6/10 | Good local approximations; production claims should be clearer. |
| Frontend UX | 7/10 | Build passes and UI is comprehensive. |
| Frontend maintainability | 5/10 | Single huge page component. |
| Dependency hygiene | 6/10 | Missing optional installs locally; no dev requirements split. |
| Production readiness | 5/10 | Many production services are placeholders/adapters. |

## Recommended Fix Order

1. Fix mode consistency:
   - Add `focused`, `comprehensive`, `adaptive` multipliers everywhere, or remove them from the API model.

2. Make tests pytest-compatible:
   - Guard script execution.
   - Convert checks to assertions.
   - Add async pytest support.

3. Restore fresh setup files:
   - Add `.env.example`.
   - Add `backend/requirements-local.txt` or fix `run-backend-linux.sh`.
   - Keep README, `run.txt`, and scripts aligned.

4. Split dependencies:
   - Base, dev, ML/OCR, production.
   - Add `pytest` to dev requirements.

5. Improve matrix runner:
   - Use longer HTTP timeouts.
   - Add `flush=True`.
   - Query final job status even after request timeout.

6. Reduce local runtime write pressure:
   - Batch event writes.
   - Compact or rotate event logs.
   - Avoid rewriting full event state on every event.

7. Implement or relabel workers:
   - Either wire Redis Streams or mark worker services as placeholders.

8. Split `frontend/app/page.tsx` into components and hooks.

9. Add production readiness checks:
   - Strict production health.
   - Docker integration tests.
   - Real store write/read tests.

10. Wire production indexing/storage:
   - Postgres records/jobs/events.
   - Redis queue/consumer groups.
   - OpenSearch BM25.
   - Qdrant vectors.
   - Neo4j relationship writes.
   - MinIO raw archive.

## Final Verdict

ASAGUS Scraper 3.0 is a capable local operator console and research prototype. It is not yet a production-ready distributed scraper despite the architecture documents describing a full 10-layer production system. The core local pipeline is alive, but the test suite, fresh setup flow, and production worker/storage/index integrations need immediate cleanup.

Best current use:
- Local preview.
- Controlled operator testing.
- Architecture experimentation.
- Offline pipeline validation.

Not yet ready for:
- CI without test refactor.
- Fresh no-Docker setup using current scripts.
- Production distributed crawling.
- Claims of fully implemented Redis/Postgres/OpenSearch/Qdrant/Neo4j/MinIO pipeline.
