# ASAGUS Scraper v3 — Cross-Check & Counter-Verification Report

**Date:** 2026-06-03  
**Method:** All claims were verified by pulling **live source code directly from the repository** at  
`https://github.com/ghulam36460/scrapper/tree/main/asagus-scraper-v3`  
**Files fetched live:** `main.py`, `models.py`, `browser.py`, `fetch.py`, `job_helpers.py`,  
`antibot_orchestrator.py`, `antibot_layer6_native.py`, `captcha_solver.py`,  
`enrichment.py`, `extraction.py`, `retrieval.py`, `storage.py`, `schema.sql`,  
`workers/async_worker.py`, `workers/indexer_worker.py`, `native/src/browser_patcher.c`

---

## Summary Verdict

The original bug report (`CODE_REVIEW_BUG_REPORT_2026_06_03.md`) is **highly accurate overall**.  
Of 8 Critical Bugs reported, **7 are fully confirmed** by live code. **1 is partially wrong** (Bug #4 — the specific claim about `enable_native_layer` not being mapped is **incorrect**; the code does map it). Two nuances were also found in Bug #2 that the report overstated slightly. All major architecture gaps are confirmed correct.

---

## Critical Bugs — Verified One by One

### Bug #1 — `antibot_preset` Exposed But Ignored
**Report verdict:** Critical  
**Code verification:** ✅ CONFIRMED CORRECT

**Evidence from `models.py` (line 233):**
```python
antibot_preset: Literal["high-stealth", "balanced", "high-speed"] = Field(
    default="balanced",
    description="Antibot stealth configuration preset: 'high-stealth' uses Camoufox ..."
)
```

**Evidence from `main.py` (lines 480–521 — the entire run_job `FetchLayer` construction):**
```python
fetcher = FetchLayer(
    enable_network_fetch=effective_network_fetch,
    proxy_manager=proxy_manager,
    browser_pool=ChromiumBrowserPool(
        pool_size=max(resource_profile.browser_contexts, 1),
        timeout_ms=job.request.max_seconds_per_page * 1000,
        engine=settings.browser_automation_engine,   # <-- global setting, NEVER job.request.antibot_preset
        headless=settings.browser_headless,
        camoufox_binary_path=settings.camoufox_binary_path,
    ),
)
```

`job.request.antibot_preset` is **never read** anywhere in `main.py`. There is zero grep match. The browser engine is hardwired to the **global** `settings.browser_automation_engine`, regardless of what preset the user selects per job. The report's description of impact and fix is accurate.

---

### Bug #2 — Dynamic Fetch Uses Plain Headless Chromium
**Report verdict:** Critical  
**Code verification:** ✅ CONFIRMED — but with one important nuance the report overstated

**What the report correctly identified:**
- `ChromiumBrowserPool.state()` explicitly reports `"challenge_bypass": False`
- `antibot_preset` does not control the browser engine
- `AntiBotOrchestrator` is not used in the real job path

**The nuance (minor correction to the report):**  
`ChromiumBrowserPool` is NOT always plain Chromium. Its `_render_with_selected_engine()` method does support Camoufox, Patchright, and nodriver. When `engine="auto"` it tries them in order:
```python
engines = ["camoufox", "patchright", "nodriver"]
```
…and only falls back to plain Playwright Chromium if all three are unavailable. So it is **not always plain Chromium** — it depends on what is installed and the **global** `settings.browser_automation_engine`, not the per-job `antibot_preset`.

The core bug stands: the preset the user submits per-job has no effect. But the statement "active browser path has no Camoufox/Patchright" is true *at deployment time* when those binaries aren't installed, and `challenge_bypass: False` is always hardcoded in the state output regardless.

---

### Bug #3 — AntiBotOrchestrator Exists But Not Integrated
**Report verdict:** Critical  
**Code verification:** ✅ CONFIRMED CORRECT

Running `grep -n "AntiBotOrchestrator\|antibot_orchestrator\|create_antibot"` against the live `main.py` returns **zero matches**. The orchestrator is imported nowhere in the production API runner. It exists only as a standalone module used in examples. The report is entirely correct.

---

### Bug #4 — `enable_native_layer` Not Mapped in `create_antibot_orchestrator_from_config`
**Report verdict:** Critical  
**Code verification:** ❌ **NOT CONFIRMED — THIS BUG IS INCORRECT IN THE REPORT**

The report states:
> `create_antibot_orchestrator_from_config()` maps only a subset of loaded configuration into `AntiBotConfig`. It does not pass `enable_native_layer` or `native_backend`.

**Actual code in `antibot_orchestrator.py` (lines 658–665):**
```python
antibot_config = AntiBotConfig(
    framework_priority=full_config.global_config.framework_priority,
    stealth_approach=StealthApproach[full_config.global_config.stealth_approach],
    tls_fingerprint=BrowserTLSFingerprint[full_config.global_config.tls_fingerprint],
    device_profile_name=full_config.global_config.device_profile,
    enable_behavioral_simulation=full_config.global_config.enable_behavioral,
    enable_native_layer=full_config.global_config.enable_native_layer,   # <-- IS mapped
    native_backend=full_config.global_config.native_backend,             # <-- IS mapped
    browser_automation_engine=browser_engine,
)
```

Both `enable_native_layer` and `native_backend` **are** explicitly mapped. This specific claim in the bug report is **false**. However, this does not affect the broader conclusion about Layer 6, because `AntiBotOrchestrator` itself is never called from `run_job()` (Bug #3), so the config mapping is moot for actual job execution.

---

### Bug #5 — CAPTCHA Solving Is Placeholder Code
**Report verdict:** Critical  
**Code verification:** ✅ CONFIRMED CORRECT

**Evidence from `captcha_solver.py`:**

For reCAPTCHA v2 (lines 290–293):
```python
self.logger.warning("YOLOv8 solver not yet implemented - placeholder")
pass
...
self.logger.warning("reCAPTCHA solver requires YOLOv8 model (not loaded)")
```

For hCaptcha (lines 337–346):
```python
self.logger.warning("hCaptcha solver requires ML models (not loaded)")
return False
...
self.logger.warning("hCaptcha ML solver not yet implemented - placeholder")
return False
```

For Cloudflare Turnstile (lines 369–401): waits a random delay then returns `False`.

The documentation claiming "reCAPTCHA v2 100% accuracy" and "hCaptcha 95.9% accuracy" are **not backed by any implementation**. The detection code exists; the solving code does not. The report's findings are precise and correct.

---

### Bug #6 — Layer 6 Native Implementation Is Mostly Aspirational
**Report verdict:** Critical  
**Code verification:** ✅ CONFIRMED CORRECT

**Evidence from `native/src/browser_patcher.c` (lines 238–247):**
```c
// Linux implementation using ptrace
printf("Linux browser patching not fully implemented (requires ptrace)\n");
// TODO: Full implementation using ptrace and /proc/pid/maps
return -1;
...
return -1;
```

Linux is the primary deployment target, and the browser patcher explicitly returns `-1` (failure) on it.

**Evidence from `antibot_layer6_native.py` `apply_native_patches()` (lines 609–617):**
```python
if self.browser_patcher.is_available():
    # Would patch browser process here
    self.logger.info("✓ Native browser patches applied")
else:
    self.logger.info("⊘ Browser patching not available, skipping")
```

The actual patching logic is a **comment** ("Would patch browser process here") followed by a log line. Nothing is patched. The report's description is accurate.

---

### Bug #7 — `require_email` Does Not Enforce Email Requirement
**Report verdict:** High  
**Code verification:** ✅ CONFIRMED CORRECT

**Evidence from `main.py` (lines 907–916):**
```python
if job.request.require_email and not extracted.email:
    await emit(
        job_id,
        LayerName.extraction,
        "email_required_note",
        "Record is missing email, but partial business leads are retained to avoid data loss",
        extracted.model_dump(),
    )
# <-- NO `continue` or `return` here. Execution continues to enrich and store the record.
await runtime.update_job(job_id, progress_message="Enriching and deduping")
enriched = await enrichment.enrich(extracted, ...)
```

When `require_email=True` and there is no email, the code emits an informational note and **continues processing and storing the record**. There is no filter. The report is correct.

---

### Bug #8 — Per-Job `enable_network_fetch=True` Cannot Enable Network When Globally Disabled
**Report verdict:** High  
**Code verification:** ✅ CONFIRMED CORRECT

**Evidence from `job_helpers.py` (lines 41–44):**
```python
def effective_runtime_flags(request: ScrapeStartRequest, settings: Settings) -> tuple[bool, bool]:
    return (
        settings.enable_network_fetch and request.enable_network_fetch is not False,
        settings.enable_search_discovery and request.enable_search_discovery is not False,
    )
```

The logic is `global AND (per_job is not False)`. This means:
- If global is `False` → result is always `False` regardless of per-job value
- Per-job `True` has **no power to override** a globally disabled network fetch

The API docs/model comments state "per-job controls can force a job into real mode" — this is **incorrect**. The report is right.

---

## Major Architecture Gaps — Verified

### Gap 1 — Redis Streams Architecture Is Not Implemented
**Code verification:** ✅ CONFIRMED

`workers/async_worker.py` in full:
```python
async def main() -> None:
    """Async worker placeholder.
    Production mode consumes Redis Streams: ...
    The API currently runs a local in-process pipeline for first-run usability.
    """
    while True:
        await asyncio.sleep(60)
```

`workers/indexer_worker.py` in full:
```python
async def main() -> None:
    """Dedicated indexer placeholder for OpenSearch, Qdrant and Neo4j writes."""
    while True:
        await asyncio.sleep(60)
```

Both workers are infinite sleep loops. No Redis Streams consumer logic exists. The entire pipeline runs as an in-process sequential coroutine in `run_job()`.

---

### Gap 2 — Persistence Does Not Write to `businesses` Table
**Code verification:** ✅ CONFIRMED

The blueprint's `schema.sql` correctly defines a `businesses` table with full typed columns (lat, lng, google_maps_id, isic_code, etc.).

But `storage.py` `_mirror_record_to_postgres()` does NOT write to `businesses`. It creates and writes to a generic `records` table:
```python
CREATE TABLE IF NOT EXISTS records (
    id TEXT PRIMARY KEY,
    source_url TEXT,
    payload JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
...
INSERT INTO records (id, source_url, payload, updated_at) VALUES (...)
```

All typed column structure is discarded into a single JSONB blob. The `businesses` table from `schema.sql` is never written to by the current storage layer.

---

### Gap 3 — Extraction Selector Store Is In-Memory, Not Persistent
**Code verification:** ✅ CONFIRMED

`extraction.py` (line 84):
```python
_selector_store: dict[str, SelectorFingerprint] = {}
```
This is a class-level dictionary (not instance-level), so it exists only for the lifetime of the process. Restarting the server loses all learned selectors. The stored selector value is literally `f"auto::{field_name}"` — a label, not a real CSS selector path.

---

### Gap 4 — Enrichment Has No Geocoding
**Code verification:** ✅ CONFIRMED

No reference to `lat`, `lng`, `latitude`, `longitude`, `geopy`, or `Nominatim` exists anywhere in `enrichment.py`. The `EnrichedRecord` `lat`/`lng` fields are never populated by the enrichment layer. The blueprint's "85% valid geocoordinates" target is not achievable.

---

### Gap 5 — Retrieval Is Local Approximation, Not Production Hybrid Search
**Code verification:** ✅ CONFIRMED

Code comments within `retrieval.py` are self-documenting on this point:
```python
notes="Hash embeddings locally; sentence-transformer/Qdrant adapter for production vectors."
notes="Implemented locally; maps to OpenSearch BM25 in production."
notes="Token-pair cross score implemented; BERT cross-encoder adapter ready."
```

The local implementation uses blake2b hash-based vectors and an in-memory inverted index. Qdrant and OpenSearch are not called in the active retrieval path.

---

## Library Usage Analysis — Verified

The `LIBRARY_USAGE_ANALYSIS.md` report was also cross-checked against the live code.

| Claim in Library Report | Code Verdict |
|---|---|
| curl-cffi is ✅ ACTIVE in fetch.py with `impersonate='chrome124'` | ✅ CONFIRMED — `fetch.py` lines 12, 79, 112–116 confirm active usage |
| Camoufox ❌ NOT INTEGRATED (only placeholder paths) | ⚠️ PARTIALLY WRONG — `browser.py` has real `_render_with_camoufox()` integration that calls `camoufox_integration.py`. It IS integrated. But it is only triggered by the **global** `settings.browser_automation_engine`, not by `antibot_preset`. The "NOT INTEGRATED" label should be "NOT WIRED TO PER-JOB PRESET". |
| Patchright ❌ NOT INTEGRATED | ⚠️ SAME as Camoufox — `browser.py` has real `_render_with_patchright()` that calls `patchright_integration.py`. It is globally available but not per-job. |
| Layer 6 native ✅ ARCHITECTURE with source files | ✅ CONFIRMED — Source exists but Linux patching returns -1 (failure). "Architecture" is accurate; "functional" is not. |
| CAPTCHA solving ❌ MISSING | ✅ CONFIRMED — Placeholder logs and `return False` confirmed in live code. |
| Layer 3 TLS (curl-cffi) fully implemented | ✅ CONFIRMED — curl-cffi with chrome124 impersonation is the first-choice static fetcher. Falls back to plain httpx only on curl-cffi failure. |
| Layer 5 Behavioral (mouse/typing) ✅ EXCELLENT | Cannot directly verify without running the code, but `antibot_layer5_behavior.py` module exists and is imported — assessment is likely accurate for the module in isolation. Whether it is called in the active job path would require tracing the full orchestrator (which is itself not wired into `run_job()`). |

**Net correction for the Library Analysis:** Camoufox and Patchright are more integrated than the "❌ NOT INTEGRATED" rating suggests — they have real implementation code in `browser.py`. The correct status is "INTEGRATED AS FALLBACK IN GLOBAL BROWSER POOL — NOT WIRED TO PER-JOB ANTIBOT PRESET".

---

## One-Page Correction Summary

The following table summarises every confirmed or corrected finding:

| # | Reported Bug / Gap | Verified? | Correction / Note |
|---|---|---|---|
| Bug 1 | `antibot_preset` ignored in `run_job()` | ✅ CONFIRMED | No grep match for `antibot_preset` in `main.py` |
| Bug 2 | Dynamic fetch uses plain headless Chromium | ✅ CONFIRMED (with nuance) | Browser pool CAN use Camoufox/Patchright but only via global setting, not per-job preset |
| Bug 3 | `AntiBotOrchestrator` not in production path | ✅ CONFIRMED | Zero imports in `main.py` |
| Bug 4 | `enable_native_layer` not mapped in config factory | ❌ INCORRECT | Live code at lines 664–665 DOES map both fields |
| Bug 5 | CAPTCHA solving is placeholder | ✅ CONFIRMED | Both reCAPTCHA and hCaptcha return `False` / log warnings |
| Bug 6 | Layer 6 native mostly aspirational | ✅ CONFIRMED | Linux patcher returns `-1`; `apply_native_patches()` is a log statement |
| Bug 7 | `require_email=True` doesn't filter | ✅ CONFIRMED | No `continue`/skip after the event emit |
| Bug 8 | Per-job network enable cannot override global | ✅ CONFIRMED | `settings.enable_network_fetch AND ...` — per-job can only disable |
| Gap 1 | Redis Streams workers are placeholders | ✅ CONFIRMED | Both workers are `while True: sleep(60)` |
| Gap 2 | Storage writes to `records` not `businesses` | ✅ CONFIRMED | JSONB blob in generic table; `businesses` schema never written |
| Gap 3 | Selector store is in-memory | ✅ CONFIRMED | Class-level dict; lost on restart |
| Gap 4 | No geocoding in enrichment | ✅ CONFIRMED | Zero lat/lng/geopy references in `enrichment.py` |
| Gap 5 | Retrieval is local hash approximation | ✅ CONFIRMED | Notes in code say "local; maps to Qdrant/OpenSearch in production" |
| Library: Camoufox "NOT INTEGRATED" | ⚠️ PARTIALLY WRONG | Module IS integrated in browser.py; the error is that it's not preset-driven |
| Library: Patchright "NOT INTEGRATED" | ⚠️ PARTIALLY WRONG | Same as Camoufox above |

---

## Verified Priority Fix List

Listed in order of correctness-impact and user-visibility:

**Fix immediately (1–3 days):**
1. Wire `antibot_preset` into `ChromiumBrowserPool(engine=...)` construction in `run_job()`:
   - `high-stealth` → `engine="camoufox"`
   - `balanced` → `engine="patchright"`
   - `high-speed` → `engine="playwright"` (fast, no stealth)
2. Add `continue` after the `email_required_note` emit when `require_email=True` and email is absent.
3. Fix `effective_runtime_flags()` comment and documentation. Either permit per-job override with operator auth, or update all docs/UI to say "per-job can only disable, never enable."
4. Remove Bug #4 from the bug report — it is not a real bug.

**Fix within 1–2 weeks:**
5. Storage layer: write to `businesses` table instead of generic `records`. Use typed column inserts matching `schema.sql`.
6. Emit an explicit `preset_engine_override` event in job output so operators can see which browser engine is actually active.
7. Add a job-start health check that reports whether Camoufox/Patchright/nodriver binaries are actually installed, so operators know preset selection will work before submitting jobs.

**Fix within 1 month:**
8. Implement real worker logic in `async_worker.py` and `indexer_worker.py` to consume Redis Streams, or document prominently that the system is single-process only.
9. Add geocoding in `enrichment.py` using `geopy`/Nominatim (already in `requirements.txt`) — even a basic pass populates `lat`/`lng` and moves the system closer to the blueprint target.
10. Move `_selector_store` to a persistent Redis or Postgres-backed store so selector learning survives restarts.

---

## Overall Project Status (Code-Verified)

| Area | Blueprint Claims | Verified Status |
|---|---|---|
| Active scraping pipeline | Full 10-layer architecture | In-process sequential coroutine; functional for basic cases |
| Anti-bot presets | High-stealth (Camoufox), Balanced (Patchright), High-speed | Preset field exists, has zero effect on execution |
| Camoufox / Patchright / nodriver | Active in job path | Available globally but not per-job; fallback on unavailability |
| CAPTCHA solving | 100% reCAPTCHA, 95.9% hCaptcha | Placeholder `return False` |
| Native Layer 6 | OS-level browser patching | Linux returns -1; only logs are produced |
| Redis Streams workers | Decoupled layer consumers | `sleep(60)` infinite loops |
| Postgres persistence | Writes to typed `businesses` schema | Writes to generic `records` JSONB table |
| Geocoding | 85% valid coordinates target | Not implemented; no lat/lng in enrichment |
| Selector self-healing | Persistent DOM fingerprint store | In-memory class dict, lost on restart |
| Retrieval | Qdrant HNSW + OpenSearch BM25 + reranking | Local hash vectors + in-memory inverted index |
| Test coverage | Not assessed in bug report | Only `ComputeAccelerator` tests found; all core path untested |

**Bottom line:** The project is a well-structured local-first demo. It is not the production ASAGUS 3.0 blueprint described in the documentation. The gap is significant but closable with methodical work over 2–3 months. The bug report's analysis is rigorous and accurate except for Bug #4 and the minor characterisation of Camoufox/Patchright as "not integrated."

---

## Implementation Update — 2026-06-03

This cross-check remains preserved as the verification record. The first corrective pass has now been applied with educational/research semantics:

| Cross-Checked Item | Current Status |
| --- | --- |
| Bug #1 — `antibot_preset` exposed but ignored | Fixed. The active job path now calls `antibot_preset_plan()` and passes its resolved browser engine into `ChromiumBrowserPool`. |
| Bug #2 — dynamic fetch relies on global browser setting | Partially fixed. Per-job presets now select Camoufox, Patchright, or Playwright preference; optional integrations still fall back if unavailable. |
| Bug #3 — orchestrator not integrated | Still not fully integrated. The active fetch path is now preset-aware, but the standalone `AntiBotOrchestrator` remains a research adapter outside `run_job()`. |
| Bug #4 — native config mapping | Confirmed as already correct in the cross-check; no fix required. The active preset plan also avoids claiming native Layer 6 use. |
| Bug #5 — CAPTCHA placeholder | Still placeholder. The active strategy reports no CAPTCHA/challenge bypass and keeps manual review handling. |
| Bug #6 — Layer 6 aspirational | Still aspirational. The active research preset plan marks native use as not requested. |
| Bug #7 — `require_email` not enforced | Fixed. Missing-email records are skipped before enrichment/storage when required. |
| Bug #8 — per-job network override blocked | Fixed. Explicit per-job `True` or `False` now overrides backend defaults for research jobs. |

Files updated:

- `backend/asagus/services/job_helpers.py`
- `backend/asagus/main.py`
- `backend/asagus/models.py`
- `backend/tests/test_research_runtime_controls.py`
- `backend/test_audit.py`
- `frontend/app/page.tsx`
- `frontend/lib/api.ts`

Verification:

- New focused backend tests passed: `5 passed`.
- Python compile checks passed for the changed backend modules.
- Frontend TypeScript compile passed with `npx tsc --noEmit`.

Remaining larger gaps from this report are still valid: Redis Stream workers, typed `businesses` persistence, persistent selector storage, geocoding, real CAPTCHA/model integrations, and full Layer 6 implementation remain future research work.
