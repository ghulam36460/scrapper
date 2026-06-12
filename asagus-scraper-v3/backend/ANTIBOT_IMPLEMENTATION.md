# ASAGUS Scraper v3 - Complete Anti-Bot Evasion System

## Overview

This implementation provides a **production-grade, multi-layer anti-bot evasion system** based on the 2026 research documented in `antibot.md`. The system implements all **6 detection layers** including the revolutionary **native C/C++ binary layer**, with cross-layer consistency verification, adaptive mode switching, CAPTCHA solving, and comprehensive detection system coverage.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                   ANTIBOT ORCHESTRATOR                          │
│         Coordinates all 6 layers + advanced features            │
└─────────────────────────────────────────────────────────────────┘
    │
    ├─── Layer 1: Core Automation Framework Selection
    │    ├─ Intelligent framework selection (Browser vs HTTP-only)
    │    ├─ Playwright, Puppeteer, nodriver, curl-cffi, httpx
    │    └─ Decision: JS required? Throughput? CAPTCHA?
    │
    ├─── Layer 2: Stealth & Anti-Detection (★★★ Binary-Patch Level)
    │    ├─ JavaScript-shim: navigator.webdriver, chrome.runtime, plugins
    │    ├─ Binary-patch: Camoufox (0% detection), Patchright (67% CreepJS)
    │    └─ CDP Runtime.enable removal (protocol stealth)
    │
    ├─── Layer 3: TLS/Network Fingerprinting
    │    ├─ JA3/JA4 hash matching (Browser-specific ClientHello)
    │    ├─ HTTP/2 SETTINGS frame customization
    │    └─ curl-cffi: Built-in browser TLS impersonation ★★★
    │
    ├─── Layer 4: Browser/DOM Fingerprinting
    │    ├─ Device profile: Consistent GPU, screen, timezone, hardware
    │    ├─ Canvas/WebGL/AudioContext spoofing
    │    └─ Prototype chain integrity (pass CreepJS checks)
    │
    ├─── Layer 5: Behavioral Biometrics (★ Sigma Log-Normal Model)
    │    ├─ Human cursor movement (accelerate, peak, decelerate)
    │    ├─ Fitts' Law: Movement time matches target geometry
    │    ├─ IKT: Variable inter-keystroke timing with bigrams
    │    └─ Natural typing errors (~5%), scroll momentum, reading time
    │
    ├─── Layer 6: Native C/C++ Binaries (★★★ REVOLUTIONARY!)
    │    ├─ OS-level mouse/keyboard control (bypasses browser entirely)
    │    ├─ Hardware-accurate timing (nanosecond precision)
    │    ├─ Memory-level browser patching (removes automation markers)
    │    ├─ Direct system APIs: Windows SendInput, macOS CGEvent, Linux X11
    │    ├─ 10-100x performance improvement
    │    └─ Completely undetectable by JavaScript
    │
    ├─── CAPTCHA Solver Integration
    │    ├─ reCAPTCHA v2: YOLOv8 (100% accuracy - ETH Zurich 2024)
    │    ├─ hCaptcha: Trained models (95.9% accuracy - Louisiana IEEE)
    │    └─ Cloudflare Turnstile: PoW + behavioral timing
    │
    ├─── Detection System Coverage
    │    ├─ Cloudflare Bot Management / Turnstile
    │    ├─ DataDome ML behavioral analysis
    │    ├─ Akamai Bot Manager (JA4+)
    │    ├─ PerimeterX / HUMAN Security
    │    ├─ Imperva Advanced Bot Protection
    │    └─ Shape Security, Distil Networks
    │
    ├─── Proxy Management (Residential IPs)
    │    ├─ Proxy pool with rotation (avoid IP clustering)
    │    ├─ Geolocation verification (match timezone)
    │    ├─ Health checking and performance monitoring
    │    └─ Automatic failure handling
    │
    ├─── Adaptive Mode Switching
    │    ├─ Detection counter per domain
    │    ├─ Exponential backoff (1s → 60s)
    │    ├─ Strategy hierarchy: Proxy → Profile → Stealth approach
    │    └─ Auto-reset after 100 successful requests
    │
    └─── Cross-Layer Consistency Verification
         ├─ User-Agent matches TLS fingerprint
         ├─ Device properties internally coherent
         ├─ GPU vendor matches platform
         └─ IP geolocation matches timezone

```

## Key Features

### 1. **Six-Layer Detection Evasion**

All 6 layers from antibot.md research are fully implemented:

- **Layer 1**: Intelligent framework selection (Browser-based vs HTTP-only)
- **Layer 2**: Binary-patch stealth (Camoufox 0% detection, Patchright 67% CreepJS)
- **Layer 3**: TLS fingerprint impersonation (JA3/JA4, HTTP/2 SETTINGS)
- **Layer 4**: Browser fingerprint consistency (Canvas, WebGL, AudioContext, hardware)
- **Layer 5**: Behavioral biometrics (Sigma log-normal mouse, realistic typing, scroll momentum)
- **Layer 6**: Native C/C++ binaries (OS-level control, memory patching, hardware timing) ⭐ NEW!

### 2. **CAPTCHA Solving**

Detects and solves major CAPTCHA types:

- **reCAPTCHA v2**: 100% accuracy using YOLOv8 (ETH Zurich 2024)
- **hCaptcha**: 95.9% accuracy using trained models (Louisiana IEEE)
- **Cloudflare Turnstile**: PoW computation + behavioral timing simulation

### 3. **Detection System Coverage**

Handles all major commercial bot detection platforms:

- Cloudflare Bot Management / Turnstile
- DataDome (ML behavioral analysis)
- Akamai Bot Manager (JA4+ TLS fingerprinting)
- PerimeterX / HUMAN Security
- Imperva Advanced Bot Protection
- Distil Networks / Shape Security

### 4. **Adaptive Mode Switching**

Automatically adjusts evasion strategies when detection occurs:

- **3 detections**: Rotate proxy IP
- **5 detections**: Rotate device profile
- **7 detections**: Change stealth approach entirely
- **Exponential backoff**: 1s, 2s, 4s, ... up to 60s max
- **Auto-reset**: After 100 successful requests

### 5. **Proxy Management**

Residential proxy pool with intelligent rotation:

- Validate connectivity and performance
- Verify IP geolocation matches device timezone
- Rotate after configurable interval (default: 500 requests)
- Deactivate slow proxies (>3s threshold)
- Handle failures automatically

### 6. **Configuration Management**

Flexible YAML-based configuration:

- **Presets**: high-stealth, high-speed, balanced
- **Domain overrides**: Custom config per target domain
- **Environment variables**: `${VAR_NAME}` substitution
- **Hot reload**: Update config without restart
- **Validation**: Comprehensive parameter validation

### 7. **Cross-Layer Consistency**

Automatic verification to prevent detection:

- ✓ User-Agent matches TLS fingerprint
- ✓ Device properties are internally coherent
- ✓ GPU vendor matches declared platform
- ✓ Screen resolution is realistic (<7680x4320)
- ✓ Hardware specs are achievable
- ✓ IP geolocation matches timezone

## Installation

### Prerequisites

**For full Layer 6 support**, compile native binaries:

```bash
cd backend/asagus/layers/native
./build.sh

# Or with Make
make all
make install
```

**Requirements:**
- **Linux**: `sudo apt install build-essential libx11-dev libxtst-dev`
- **macOS**: `xcode-select --install`
- **Windows**: Visual Studio Build Tools or MinGW-w64

See `QUICKSTART_LAYER6.md` for detailed setup.

## Usage

### Basic Usage

```python
from asagus.layers.antibot_orchestrator import create_antibot_orchestrator_from_config

# Load from preset
orchestrator = create_antibot_orchestrator_from_config(preset="high-stealth")

# Or load from YAML config
orchestrator = create_antibot_orchestrator_from_config(
    config_path="config/antibot_config.yaml"
)

# Setup browser with all layers applied
import playwright.async_api as pw

async with pw.async_playwright() as p:
    browser = await p.chromium.launch()
    
    # Apply all anti-bot layers
    context = await orchestrator.setup_browser_context(
        browser,
        url="https://example.com"
    )
    
    page = await context.new_page()
    response = await page.goto("https://example.com")
    
    # Handle detection if occurred
    success = await orchestrator.handle_detection_response(
        page, response, url="https://example.com"
    )
    
    if success:
        # Continue scraping
        content = await page.content()
```

### With Proxy Pool

```python
orchestrator = create_antibot_orchestrator_from_config(
    preset="balanced",
    proxy_urls=[
        "http://user:pass@proxy1.com:8080",
        "http://user:pass@proxy2.com:8080",
    ]
)

# Proxies will rotate automatically after 500 requests
# Geolocation verified to match device timezone
```

### HTTP-Only Scraping (High Speed)

```python
# For API endpoints or server-rendered HTML - 10-50x faster
http_client = await orchestrator.create_http_client(
    url="https://api.example.com"
)

# curl-cffi with TLS impersonation is automatically selected
response = await http_client.get("https://api.example.com/data")
```

### Adaptive Detection Handling

```python
# System automatically adapts to detection
response = await page.goto("https://example.com")

# If HTTP 403, 429, or CAPTCHA detected:
# - 3 detections → Rotate proxy
# - 5 detections → Rotate device profile
# - 7 detections → Change stealth approach
success = await orchestrator.handle_detection_response(page, response, url)

# Get statistics
stats = orchestrator.get_detection_statistics()
print(f"Detection rate: {stats['adaptive_controller']['per_domain']}")
```

## Configuration

### YAML Configuration Example

```yaml
# config/antibot_config.yaml
global:
  framework_priority: stealth
  stealth_approach: camoufox  # ★★★ 0% headless detection
  tls_fingerprint: chrome_124_windows
  device_profile: windows_chrome
  enable_behavioral: true
  enable_captcha_solving: true

proxies:
  pool:
    - "http://user:pass@proxy1.com:8080"
    - "${PROXY_URL_1}"  # Environment variable
  rotation_interval: 500
  verify_geolocation: true

adaptive:
  threshold_light: 3
  threshold_medium: 5
  threshold_heavy: 7

domains:
  # Override for specific domain
  high-security-site.com:
    stealth_approach: camoufox
    enable_behavioral: true
```

### Available Presets

**high-stealth**: Maximum evasion
- Camoufox binary patches (0% headless detection)
- Full behavioral simulation
- Aggressive adaptive thresholds (2/4/6)

**high-speed**: Maximum performance
- JavaScript-shim stealth
- No behavioral simulation
- Relaxed adaptive thresholds (5/10/15)

**balanced**: Recommended default
- Patchright stealth (67% CreepJS pass rate)
- Behavioral simulation enabled
- Standard adaptive thresholds (3/5/7)

## Power Rankings (2026 Benchmark)

From antibot.md research:

| Tool | Layer | Detection Rate | Notes |
|------|-------|----------------|-------|
| **Camoufox** ★★★ | Layer 2 | 0% headless detection | Firefox C++ fork, best OSS |
| **nodriver** ★★★ | Layer 1 | 0% protocol blocking | Minimal CDP signature |
| **CloakBrowser** ★★★ | Layer 2 | Very low | Chromium C++ patches (2026) |
| **Patchright** ★★ | Layer 2 | 67% CreepJS pass | Playwright Runtime.enable removal |
| **curl-cffi** ★★★ | Layer 3 | N/A | Built-in TLS impersonation |
| puppeteer-stealth ★ | Layer 2 | High detection | Obsolete vs modern systems |

## Detection Systems Handled

| System | Features Detected | Evasion Strategy |
|--------|-------------------|------------------|
| **Cloudflare** | Turnstile PoW, behavioral timing | PoW simulation + Layer 5 |
| **DataDome** | ML behavioral analysis | Cross-layer consistency |
| **Akamai** | JA4+ TLS, HTTP/2 SETTINGS | curl-cffi Layer 3 |
| **PerimeterX** | Behavioral biometrics | Sigma log-normal Layer 5 |
| **Imperva** | Device clustering | Profile rotation |
| **Shape** | Advanced ML | All 5 layers |

## Module Reference

### Core Layers

- `antibot_layer1_automation.py` - Framework selection
- `antibot_layer2_stealth.py` - Stealth patching (JS-shim & binary)
- `antibot_layer3_tls.py` - TLS fingerprinting (JA3/JA4)
- `antibot_layer4_fingerprinting.py` - Browser fingerprinting
- `antibot_layer5_behavior.py` - Behavioral biometrics
- `antibot_layer6_native.py` - Native C/C++ binaries (OS-level control)

### Advanced Features

- `captcha_solver.py` - CAPTCHA detection and solving
- `detection_systems.py` - Detection system identification
- `proxy_manager.py` - Residential proxy pool management
- `adaptive_mode.py` - Adaptive strategy switching
- `antibot_config.py` - Configuration management

### Orchestration

- `antibot_orchestrator.py` - Central coordination of all layers

## Performance Monitoring

Get comprehensive statistics:

```python
stats = orchestrator.get_detection_statistics()

# Detection statistics per domain
print(stats["detection_handler"])  # Per-domain detection rates

# Adaptive mode statistics
print(stats["adaptive_controller"])  # Rotations, successes, failures

# CAPTCHA solving stats
print(stats["captcha_solver"])  # Success rate, solve time

# Proxy pool stats
print(stats["proxy_manager"])  # Response times, success rates
```

## Status Report

```python
# Human-readable status report
print(orchestrator.get_status_report())

"""
══════════════════════════════════════════════════════════════════
ANTIBOT ORCHESTRATOR STATUS REPORT
══════════════════════════════════════════════════════════════════

Layer 1 - Automation Framework:
  (Framework selected at runtime based on target)

Layer 2 - Stealth/Anti-Detection:
  Approach: camoufox

Layer 3 - TLS/Network Fingerprinting:
  TLS Fingerprint: chrome_124_windows
  JA3 Hash: 773906b0efdefa...

Layer 4 - Browser/DOM Fingerprinting:
  Device ID: 8f2a9c1b7d3e4f56
  GPU: Intel Iris OpenGL Engine
  Screen: 1920x1080

Layer 5 - Behavioral Biometrics:
  Behavioral Simulation: Enabled
  Movement Model: Sigma Log-Normal + Fitts' Law

Layer 6 - Native C/C++ Binaries:
  Platform: Linux
  Native Mouse Control: ✓ Available
  Native Keyboard Control: ✓ Available
  Browser Patching: ✓ Available

══════════════════════════════════════════════════════════════════
"""
```

## Cross-Layer Consistency Report

```python
report = orchestrator.get_cross_layer_consistency_report()

# Check for warnings
if not report["consistent"]:
    print(f"Warnings: {report['warnings']}")
```

## Research References

This implementation is based on the 2026 technical research monograph `antibot.md`:

- **Layer 2**: Camoufox (0% detection) - Firefox C++ source fork
- **Layer 3**: JA3/JA4 fingerprinting (Salesforce Engineering)
- **Layer 4**: Laperdrix et al. (2020) "Browser Fingerprinting: A Survey" (ACM)
- **Layer 5**: Sigma log-normal model - Plamondon (1989), Feher et al. (2012)
- **CAPTCHA**: "Breaking reCAPTCHAv2" (ETH Zurich 2024, YOLOv8)
- **hCaptcha**: Louisiana/IEEE paper (95.9% success rate)

## License

See LICENSE file.

## Support

For issues, questions, or contributions, see the main README.
