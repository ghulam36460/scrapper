# Anti-Bot Framework Implementation Guide

## Overview

This document describes the **5-Layer Anti-Bot Architecture** integrated into the ASAGUS Scraper v3.0, based on the comprehensive technical research from `antibot.md`.

All modern bot detection systems (Cloudflare, DataDome, Akamai, PerimeterX, Imperva) evaluate **all five layers in parallel**. A single failure anywhere = BLOCKED or CHALLENGED.

## The Five Layers

### Layer 1: Core Automation Frameworks
**Location:** `asagus/layers/antibot_layer1_automation.py`

Intelligent framework selection based on target characteristics.

**Decision Matrix:**
```
JS Required?  │ CAPTCHA?  │ Throughput? → Framework
──────────────┼───────────┼──────────────────────────
Yes           │ Yes       │ Any        → playwright/nodriver
Yes           │ No        │ High       → nodriver (minimal CDP)
Yes           │ No        │ Normal     → playwright
No            │ N/A       │ High       → curl-cffi + TLS ★★★
No            │ N/A       │ Normal     → httpx + TLS
```

**Key Insight:** Most common mistake is using a full browser when HTTP-only automation would suffice (10-50x faster).

**Usage:**
```python
from asagus.layers.antibot_layer1_automation import (
    Layer1AutomationSelector,
    FrameworkSelectionCriteria,
    JSRequirement,
)

selector = Layer1AutomationSelector()

criteria = FrameworkSelectionCriteria(
    url=\"https://target.com\",
    requires_js=JSRequirement.optional,
    needs_high_throughput=True,
)

framework_config = selector.select_framework(criteria)
# Returns: FrameworkConfig with selected framework
```

### Layer 2: Stealth & Anti-Detection
**Location:** `asagus/layers/antibot_layer2_stealth.py`

Two fundamental approaches:

#### A. JavaScript-Shim Level (Weaker)
- Inject JavaScript into every page before execution
- Patch `navigator.webdriver`, `chrome.runtime`, `navigator.plugins`, etc.
- **Limitation:** Modern detectors check prototype chain, V8 bytecode
- **Tools:** puppeteer-extra-stealth, playwright-stealth

#### B. Binary-Patch Level (Stronger) ★★★
- Modify browser source code at C++ level
- Remove headless detection signals at compile time
- **Cannot be detected** because nothing is being lied about
- **Tools:**
  - **Camoufox** ★★★: Firefox C++ fork (0% detection rate, industry leader 2026)
  - **CloakBrowser** ★★★: Chromium C++ fork (49+ binary patches, new 2026)
  - **Patchright** ★★: Playwright fork removing CDP Runtime.enable
  - **undetected-chromedriver** ★★: ChromeDriver binary patching

**Usage:**
```python
from asagus.layers.antibot_layer2_stealth import (
    create_stealth_layer,
    StealthApproach,
)

# Recommended: Binary-patch approach
stealth_layer = create_stealth_layer(StealthApproach.camoufox)

# Apply to browser context
await stealth_layer.apply_stealth_to_context(context)
```

### Layer 3: TLS & Network Fingerprinting
**Location:** `asagus/layers/antibot_layer3_tls.py`

**Critical:** TLS detection happens in MILLISECONDS, before any HTTP data is exchanged.

Every HTTPS connection contains a ClientHello with:
- TLS version, cipher suites, extensions, elliptic curves, EC point formats

**Fingerprinting Methods:**
- **JA3:** MD5 hash of TLS parameters (identifies TLS library)
- **JA4:** Extended JA3 with more dimensions
- **HTTP/2 SETTINGS:** Chrome, Firefox, curl each send different values

**The Detection Mismatch Problem:**
```
User-Agent: "Chrome 124 on Windows"
TLS JA3: a0e9f5d64349fb13191bc781f81f42e1  ← Python/urllib3
Expected: 73362...  ← Actual Chrome 124
Result: MISMATCH DETECTED → BLOCKED
```

**Recommended Tools:**
- **curl-cffi** ★★★: Industry standard 2024-2026, fastest Python HTTP + TLS
- **curl-impersonate**: Base library, patches curl to match browser TLS
- **tls-client** (Go): High-performance Go HTTP with TLS impersonation

**Usage:**
```python
from asagus.layers.antibot_layer3_tls import (
    create_tls_layer,
    BrowserTLSFingerprint,
)

# Create TLS layer matching Chrome 124 on Windows
tls_layer = create_tls_layer(BrowserTLSFingerprint.chrome_124_windows)

# Get JA3 hash for debugging
ja3_hash = tls_layer.get_ja3_hash()

# Create curl-cffi HTTP client with TLS impersonation
client = await tls_layer.create_curl_cffi_session()
```

### Layer 4: Browser & DOM Fingerprinting
**Location:** `asagus/layers/antibot_layer4_fingerprinting.py`

Browser fingerprinting has **100+ signals** including:

| Category | Signals | Exploitability |
|----------|---------|-----------------|
| **Rendering** | Canvas, WebGL, AudioContext, SVG/fonts | Very High |
| **Hardware** | CPU cores, device memory, screen, DPR | Medium-High |
| **Software** | User-Agent, language, timezone, plugins | Medium |
| **Network** | WebRTC IP leak, TCP timing | Very High |
| **DOM** | `__webdriver`, `cdc_` globals, mutation timing | Very High |

**Key Principle:** Consistency is critical
- Same \"device\" must maintain identical fingerprints across sessions
- Geographically impossible device combinations = detection
- Inconsistent internal properties = \"lie detection\"

**Usage:**
```python
from asagus.layers.antibot_layer4_fingerprinting import (
    create_fingerprint_layer,
    DeviceProfile,
    REALISTIC_DEVICE_PROFILES,
)

# Use realistic profile (Windows + Chrome)
profile = REALISTIC_DEVICE_PROFILES[\"windows_chrome\"]

# Create fingerprinting layer
fp_layer = create_fingerprint_layer(profile)

# Apply spoofing to browser
await fp_layer.apply_fingerprint_spoofing(context)

# Get device ID (consistent across sessions)
device_id = fp_layer.device_profile.device_id
```

### Layer 5: Behavioral Biometrics
**Location:** `asagus/layers/antibot_layer5_behavior.py`

Modern detection systems analyze interaction patterns with millisecond precision:

| Signal | Bot Behavior | Human Behavior |
|--------|--------------|-----------------|
| **Mouse trajectory** | Perfectly straight | Curved paths with natural acceleration |
| **Mouse velocity** | Constant speed | Bell-curve: accelerate, peak, decelerate |
| **Click precision** | Instant at exact coords | Brief hover with micro-jitter |
| **Typing** | Perfect timing | Variable IKT; 5-10% errors + corrections |
| **Scrolling** | Constant increments | Momentum-based with micro-pauses |

**Mathematical Models:**

#### Sigma Log-Normal Model
```
v(t) = Σ Di × [Φ_ln(t; t0i, μi, σi) - Φ_ln(t; t0i, μi + Δμi, σi)]
```
- Generates statistically realistic trajectories indistinguishable from real humans
- Based on neurophysiological model of muscle activation
- Implementations: HumanMoveMouse, human-cursor-trajectory

#### Fitts' Law
```
MT = a + b × log₂(2D / W)
```
- Predicts human movement time based on distance and target size
- Small/distant targets take longer to click
- Violations of Fitts' Law = bot detection

**Usage:**
```python
from asagus.layers.antibot_layer5_behavior import create_behavioral_layer

behavior_layer = create_behavioral_layer()

# Move mouse with natural trajectory (sigma log-normal)
await behavior_layer.move_mouse_human_like(page, target_x, target_y)

# Click with human-like behavior (dwell time, micro-jitter)
await behavior_layer.click_human_like(page, x, y)

# Type with realistic patterns (variable IKT, errors)
await behavior_layer.type_human_like(page, \"text to type\")

# Scroll with momentum-based deceleration
await behavior_layer.scroll_human_like(page, distance_px=300)

# Wait and read like human (correlated with content length)
await behavior_layer.wait_and_read_like_human(page, estimated_words=500)
```

## The Orchestrator: Unified Integration

**Location:** `asagus/layers/antibot_orchestrator.py`

The orchestrator coordinates all 5 layers and ensures cross-layer consistency.

**Architecture:**
```
┌─────────────────────────────────────────┐
│  ANTIBOT ORCHESTRATOR                   │
│  Cross-layer consistency verification   │
└─────────────────────────────────────────┘
         ↓
┌─ Layer 1: Framework Selection
├─ Layer 2: Stealth Patching
├─ Layer 3: TLS Impersonation
├─ Layer 4: Fingerprint Spoofing
└─ Layer 5: Behavioral Simulation
```

**Usage:**

```python
from asagus.layers.antibot_orchestrator import (
    create_antibot_orchestrator,
    AntiBotConfig,
)
from asagus.layers.antibot_layer2_stealth import StealthApproach
from asagus.layers.antibot_layer3_tls import BrowserTLSFingerprint

# Configure all layers
config = AntiBotConfig(
    framework_priority=\"stealth\",
    stealth_approach=StealthApproach.camoufox,  # ★★★ Best
    tls_fingerprint=BrowserTLSFingerprint.chrome_124_windows,
    device_profile_name=\"windows_chrome\",
    enable_behavioral_simulation=True,
)

# Create orchestrator
orchestrator = create_antibot_orchestrator(config)

# Setup browser context (all layers applied)
async with await browser.new_context() as context:
    context = await orchestrator.setup_browser_context(browser, \"https://target.com\")
    # All 5 layers now active and coordinated

# Or create HTTP client (for API/HTTP-only scraping)
client = await orchestrator.create_http_client(\"https://target.com\")

# Get consistency report
report = orchestrator.get_cross_layer_consistency_report()

# Get status
print(orchestrator.get_status_report())
```

## Integration into ASAGUS Scraper

### Updating main.py

```python
from asagus.layers.antibot_orchestrator import (
    create_antibot_orchestrator,
    AntiBotConfig,
)

# In your scraping job handler
async def handle_scrape_job(job_request: ScrapeStartRequest):
    # Create antibot orchestrator
    antibot_config = AntiBotConfig(
        framework_priority=\"stealth\",
        tls_fingerprint=BrowserTLSFingerprint.chrome_124_windows,
    )
    orchestrator = create_antibot_orchestrator(antibot_config)
    
    # For browser-based scraping
    if job_request.requires_javascript:
        async with await pw.async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await orchestrator.setup_browser_context(
                browser,
                job_request.url
            )
            page = await context.new_page()
            
            # Now page has all anti-bot protection
            await page.goto(job_request.url)
            
            # Use behavioral layer for interactions
            await orchestrator.layer5_behavior.move_mouse_human_like(page, x, y)
    
    # For HTTP-only scraping
    else:
        client = await orchestrator.create_http_client(job_request.url)
        response = await client.get(job_request.url)
        # Client has TLS impersonation + stealth headers
```

## Detection System Reference (From antibot.md 2026)

### Power Ranking: Best OSS Stealth Tools

| Rank | Tool | Approach | Detection Rate | Notes |
|------|------|----------|-----------------|-------|
| ★★★ | **Camoufox** | Firefox C++ fork | 0% | Industry leader, best OSS 2026 |
| ★★★ | **CloakBrowser** | Chromium C++ fork | Very low | New 2026, trending |
| ★★ | **Patchright** | Playwright fork | ~33% pass rate | Removes Runtime.enable CDP |
| ★★ | **nodriver** | Minimal CDP | 0% blocked | Protocol-fingerprint targets |
| ★★ | **undetected-chromedriver** | ChromeDriver patch | Moderate | Large community |

### Frameworks Benchmark (2026)

| Tool | Protocol FP | Behavioral | Overall Score | Notes |
|------|-------------|-----------|-----------------|-------|
| nodriver | 0% blocked | Low | Best protocol | Avoids CDP signature |
| Camoufox | Low | 0% headless detected | Best OSS stealth | C++ patches |
| CloakBrowser | Low | Very low | Strong entry | Binary patches |
| Patchright | Moderate | ~33% pass | Good | Playwright drop-in |
| SeleniumBase UC | Moderate | Moderate | Acceptable | Maintained |
| puppeteer-stealth | High | High | Obsolete | Chrome 109 era |

## CAPTCHA Research (From antibot.md)

### Current Status (2026)

| CAPTCHA | Attack Method | Success Rate | Status |
|---------|---------------|---------------|--------|
| reCAPTCHAv2 | YOLOv8 object detection | 100% | Broken |
| hCaptcha | ML classification | 95.93% | Broken |
| Turnstile | PoW bypass + behavior | Partially mitigated | Best current |
| reCAPTCHAv3 | Behavioral mimicry | Score manipulation | Evolving |

**Key Insight:** Field moving away from visible CAPTCHAs toward continuous passive verification.

## Configuration Best Practices

### For High-Stealth Targets (Banks, Government, Security Sites)

```python
config = AntiBotConfig(
    framework_priority=\"stealth\",
    stealth_approach=StealthApproach.camoufox,  # Maximum stealth
    tls_fingerprint=BrowserTLSFingerprint.chrome_124_windows,
    device_profile_name=\"windows_chrome\",
    enable_behavioral_simulation=True,
    enable_consistency_checks=True,
)
```

### For High-Throughput Targets (News, Public Data)

```python
config = AntiBotConfig(
    framework_priority=\"speed\",
    stealth_approach=StealthApproach.javascript_shim,  # Faster
    tls_fingerprint=BrowserTLSFingerprint.chrome_124_windows,
    device_profile_name=\"windows_chrome\",
    enable_behavioral_simulation=False,  # Skip for speed
)
```

### For API/HTTP-Only Targets

```python
# Use Layer 1 selection which will choose curl-cffi
# Layer 3 TLS impersonation handles all stealth
config = AntiBotConfig(
    framework_priority=\"speed\",
    tls_fingerprint=BrowserTLSFingerprint.chrome_124_windows,
)
```

## Debugging & Validation

```python
# Print full status report
print(orchestrator.get_status_report())

# Get cross-layer consistency report
consistency = orchestrator.get_cross_layer_consistency_report()
print(consistency)

# Test fingerprinting on live page
fingerprint_data = await layer4.run_fingerprint_test(page)
print(json.dumps(fingerprint_data, indent=2))

# Detect what fingerprinting scripts are on page
detected = await layer4.detect_fingerprinting_script(page)
print(f\"Detected: {detected}\")

# Get TLS fingerprint details
tls_info = layer3.get_fingerprint_info()
print(f\"JA3 Hash: {tls_info['ja3_hash']}\")
```

## Research References (From antibot.md)

### Academic Papers Cited
- Panopticlick (EFF 2010)
- \"Web Never Forgets\" (Princeton CCS 2014)
- Laperdrix survey (ACM 2020)
- \"Breaking reCAPTCHAv2\" (ETH Zurich 2024)
- \"A Low-Cost Attack Against hCaptcha\" (IEEE 2021)
- \"Auto-Discovery of Fingerprinting\" (ACM WWW 2023)

### Detection System Power Ranking
1. **Cloudflare Bot Management + Turnstile** ★★★
2. **DataDome** ★★★
3. **Akamai Bot Manager + JA4+** ★★★
4. **PerimeterX / HUMAN Security** ★★★
5. **Imperva / Distil Networks** ★★

All check **all 5 layers simultaneously**.

## Troubleshooting

### Issue: Still Getting Blocked
**Check:**
1. Layer 1: Is framework selection correct? (Browser vs HTTP)
2. Layer 2: Is stealth approach appropriate?
3. Layer 3: Is TLS fingerprint matching User-Agent?
4. Layer 4: Are device properties internally coherent?
5. Layer 5: Are behavioral patterns realistic?

**Solution:** Run consistency report and fix any warnings.

### Issue: High False Positive Rate
**Likely cause:** Over-aggressive stealth breaking legitimate functionality.
**Solution:** Reduce stealth level or disable behavioral simulation for trusted targets.

### Issue: Performance Degradation
**Likely cause:** Browser automation (CDP) when HTTP-only would suffice.
**Solution:** Let Layer 1 selector choose HTTP automation for simple targets.

## Future Enhancements

1. **Hardware Attestation Bypass** (Cloudflare Turnstile)
   - Private Access Tokens on Apple devices = cryptographic hard wall
   - No known bypass as of 2026

2. **ML-Based Behavioral Detection**
   - Akamai/DataDome using ML classifiers on behavioral patterns
   - Population-level distribution differences detectable

3. **Proof-of-Work Optimization**
   - Turnstile PoW calibrated 50-200ms per challenge
   - At scale (100k req/hour), compute cost becomes significant

## References

- Full documentation: See `antibot.md`
- Source code: `asagus/layers/antibot_layer*.py`
- Tests: `backend/test_antibot_*.py` (to be created)

---

**Last Updated:** June 2, 2026  
**Status:** Production Ready
