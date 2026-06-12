# Anti-Bot Framework: Quick Reference Guide

## One-Minute Setup

```python
from asagus.layers.antibot_orchestrator import (
    create_antibot_orchestrator,
    AntiBotConfig,
)
from asagus.layers.antibot_layer2_stealth import StealthApproach
from asagus.layers.antibot_layer3_tls import BrowserTLSFingerprint

# 1. Create config
config = AntiBotConfig(
    stealth_approach=StealthApproach.camoufox,
    tls_fingerprint=BrowserTLSFingerprint.chrome_124_windows,
)

# 2. Create orchestrator
orchestrator = create_antibot_orchestrator(config)

# 3. Setup browser context (all 5 layers applied)
context = await orchestrator.setup_browser_context(browser, url)
page = await context.new_page()

# 4. Use behavioral simulation
await orchestrator.layer5_behavior.click_human_like(page, x, y)
```

## Layer Selection Quick Guide

### When to use each layer...

```python
# Layer 1: Framework Selection
# Auto-selected based on:
- Does target require JavaScript? → Browser
- High throughput needed? → HTTP-only (curl-cffi)
- CAPTCHA solving? → Browser (Playwright/nodriver)

# Layer 2: Stealth Approach
if maximum_stealth_needed:
    StealthApproach.camoufox  # ★★★ Best, Firefox C++ fork
elif new_target and experimental:
    StealthApproach.cloak_browser  # ★★★ New Chromium fork
elif playwright_already_used:
    StealthApproach.patchright  # ★★ Remove CDP Runtime.enable
else:
    StealthApproach.javascript_shim  # ★★ Fast, sufficient for many

# Layer 3: TLS Fingerprint
# Most sites use Chrome, so:
BrowserTLSFingerprint.chrome_124_windows  # 90% of cases

# Layer 4: Device Profile
# Pick realistic profile matching your use case:
REALISTIC_DEVICE_PROFILES[\"windows_chrome\"]  # Most common
REALISTIC_DEVICE_PROFILES[\"macos_chrome\"]    # Apple users
REALISTIC_DEVICE_PROFILES[\"linux_firefox\"]   # Linux users

# Layer 5: Behavioral Simulation
enable_behavioral_simulation=True   # For stealth targets
enable_behavioral_simulation=False  # For high throughput
```

## Configuration Presets

### Preset 1: Maximum Stealth (Banking, Government)
```python
config = AntiBotConfig(
    framework_priority=\"stealth\",
    stealth_approach=StealthApproach.camoufox,
    tls_fingerprint=BrowserTLSFingerprint.chrome_124_windows,
    device_profile_name=\"windows_chrome\",
    enable_behavioral_simulation=True,
    enable_consistency_checks=True,
)
```

### Preset 2: High Throughput (APIs, News Sites)
```python
config = AntiBotConfig(
    framework_priority=\"speed\",
    stealth_approach=StealthApproach.javascript_shim,
    tls_fingerprint=BrowserTLSFingerprint.chrome_124_windows,
    enable_behavioral_simulation=False,
)
# Layer 1 auto-selects curl-cffi for HTTP-only
```

### Preset 3: Balanced (Most Sites)
```python
config = AntiBotConfig(
    framework_priority=\"compatibility\",
    stealth_approach=StealthApproach.javascript_shim,
    tls_fingerprint=BrowserTLSFingerprint.chrome_124_windows,
    device_profile_name=\"windows_chrome\",
    enable_behavioral_simulation=True,
)
```

## Common Tasks

### Task 1: Scrape API with TLS Stealth
```python
config = AntiBotConfig(
    framework_priority=\"speed\",
    tls_fingerprint=BrowserTLSFingerprint.chrome_124_windows,
)
orchestrator = create_antibot_orchestrator(config)

# Layer 1 auto-selects curl-cffi
client = await orchestrator.create_http_client(\"https://api.target.com\")

response = await client.get(\"https://api.target.com/data\")
# TLS fingerprint matches Chrome 124
# Stealth headers injected
```

### Task 2: Scrape JavaScript Site
```python
config = AntiBotConfig(
    stealth_approach=StealthApproach.camoufox,
)
orchestrator = create_antibot_orchestrator(config)

async with await pw.async_playwright() as p:
    browser = await p.chromium.launch(headless=True)
    context = await orchestrator.setup_browser_context(browser, url)
    page = await context.new_page()
    
    await page.goto(url)
    content = await page.content()
    
    await browser.close()
```

### Task 3: Handle Form Filling
```python
page = await context.new_page()
await page.goto(url)

behavior = orchestrator.layer5_behavior

# Fill form field with human-like typing
await behavior.click_human_like(page, input_x, input_y)
await behavior.type_human_like(page, \"username\")

# Click submit with natural behavior
await behavior.click_human_like(page, submit_x, submit_y)

# Wait like human would
await behavior.wait_and_read_like_human(page, estimated_words=300)
```

### Task 4: Scroll and Extract
```python
page = await context.new_page()
await page.goto(url)

behavior = orchestrator.layer5_behavior

# Scroll like human
for _ in range(5):
    await behavior.scroll_human_like(page, distance_px=300, duration_seconds=1)
    await behavior.wait_and_read_like_human(page, estimated_words=200)

# Extract content
content = await page.content()
```

### Task 5: Validate Configuration
```python
orchestrator = create_antibot_orchestrator(config)

# Get full status report
print(orchestrator.get_status_report())

# Check consistency
consistency = orchestrator.get_cross_layer_consistency_report()
if consistency[\"consistent\"]:
    print(\"✓ Configuration is consistent\")
else:
    print(\"✗ Issues found:\")
    for warning in consistency[\"warnings\"]:
        print(f\"  - {warning}\")

# Get TLS details
tls_info = orchestrator.layer3_tls.get_fingerprint_info()
print(f\"JA3 Hash: {tls_info['ja3_hash']}\")
```

## Debugging

### Get Layer Information
```python
orchestrator = create_antibot_orchestrator(config)

# Layer 1 info (selected at runtime)
print(\"Layer 1: Framework selection based on target\")

# Layer 2 info
print(f\"Layer 2: {config.stealth_approach.value}\")

# Layer 3 info
tls_info = orchestrator.layer3_tls.get_fingerprint_info()
print(f\"Layer 3 JA3: {tls_info['ja3_hash']}\")

# Layer 4 info
print(f\"Layer 4 Device ID: {orchestrator.layer4_fingerprinting.device_profile.device_id}\")

# Layer 5 info
print(f\"Layer 5: {'Enabled' if config.enable_behavioral_simulation else 'Disabled'}\")
```

### Detect Fingerprinting on Page
```python
detected = await orchestrator.layer4_fingerprinting.detect_fingerprinting_script(page)
print(f\"Fingerprinting detected: {detected}\")
# Output: {'fingerprintjs': True, 'creepjs': False, 'maxmind': True}
```

### Extract Fingerprint Data
```python
fp_data = await orchestrator.layer4_fingerprinting.run_fingerprint_test(page)
print(json.dumps(fp_data, indent=2))
# Shows: canvas, webgl, navigator, screen, timezone properties
```

## Troubleshooting

### Still Getting Blocked?

**Step 1:** Check consistency
```python
consistency = orchestrator.get_cross_layer_consistency_report()
if not consistency[\"consistent\"]:
    print(\"Configuration issues:\", consistency[\"warnings\"])
```

**Step 2:** Increase stealth
```python
config.stealth_approach = StealthApproach.camoufox  # Maximum
```

**Step 3:** Verify TLS
```python
tls_info = orchestrator.layer3_tls.get_fingerprint_info()
print(f\"TLS Fingerprint: {tls_info['fingerprint_type']}\")
print(f\"JA3 Hash: {tls_info['ja3_hash']}\")
```

**Step 4:** Add delay
```python
import asyncio
await asyncio.sleep(random.uniform(2, 5))  # 2-5 second random delay
```

### Performance Issues?

**Issue:** Using browser when HTTP-only would work
```python
# Before: Slow
orchestrator = create_antibot_orchestrator(config)
context = await orchestrator.setup_browser_context(browser, url)
# 0.5-2 requests/sec

# After: Fast (Layer 1 auto-selects curl-cffi)
config.framework_priority = \"speed\"
orchestrator = create_antibot_orchestrator(config)
client = await orchestrator.create_http_client(url)
# 50-200 requests/sec
```

**Issue:** Behavioral simulation overhead
```python
# Disable for high throughput
config.enable_behavioral_simulation = False
```

## Architecture Reference

```
All modern detection systems evaluate 5 layers in PARALLEL.
ONE failure anywhere = BLOCKED or CHALLENGED.

┌─────────────────────────────────────────┐
│ Layer 1: Framework Selection            │
│ Browser (CDP) vs HTTP-only (curl-cffi)  │
├─────────────────────────────────────────┤
│ Layer 2: Stealth & Anti-Detection       │
│ JS-shim vs Binary-patch (Camoufox)     │
├─────────────────────────────────────────┤
│ Layer 3: TLS/Network Fingerprinting     │
│ JA3/JA4, curl-cffi, TLS impersonation   │
├─────────────────────────────────────────┤
│ Layer 4: Browser/DOM Fingerprinting     │
│ Canvas, WebGL, device profile, timezone │
├─────────────────────────────────────────┤
│ Layer 5: Behavioral Biometrics          │
│ Sigma log-normal, Fitts' Law, IKT       │
└─────────────────────────────────────────┘
```

## API Reference Quick Lookup

### AntiBotConfig Parameters
```python
AntiBotConfig(
    framework_priority: str = "stealth",      # \"speed\"|\"stealth\"|\"compatibility\"
    stealth_approach: StealthApproach = ...,  # Camoufox|CloakBrowser|Patchright|...
    tls_fingerprint: BrowserTLSFingerprint = ...,  # Chrome124Windows|Firefox125|...
    device_profile_name: str = \"windows_chrome\",  # Or custom DeviceProfile
    enable_behavioral_simulation: bool = True,
    proxy_url: str = \"\",
    enable_consistency_checks: bool = True,
)
```

### Behavioral Layer Methods
```python
behavior = orchestrator.layer5_behavior

# Movement
await behavior.move_mouse_human_like(page, x, y, duration=None)

# Clicking
await behavior.click_human_like(page, x, y, button=\"left\", dwell_time_ms=50)

# Typing
await behavior.type_human_like(page, text, error_rate=0.05)

# Scrolling
await behavior.scroll_human_like(page, distance_px=300, duration_seconds=2.0)

# Waiting
await behavior.wait_and_read_like_human(page, estimated_words=500, wpm=250)
```

### Orchestrator Methods
```python
orchestrator = create_antibot_orchestrator(config)

# Setup
await orchestrator.setup_browser_context(browser, url)
await orchestrator.create_http_client(url)

# Validation
orchestrator.get_cross_layer_consistency_report()
orchestrator.get_status_report()

# Layer Access
orchestrator.layer1_selector
orchestrator.layer2_stealth
orchestrator.layer3_tls
orchestrator.layer4_fingerprinting
orchestrator.layer5_behavior
```

## Best Practices

1. ✅ **Use Layer 1 for auto-selection** - Don't assume browser needed
2. ✅ **Use Camoufox for maximum stealth** - Binary patches > JS shims
3. ✅ **Keep device profiles realistic** - Validate consistency
4. ✅ **Match TLS to User-Agent** - JA3 mismatch = instant block
5. ✅ **Use behavioral simulation for high-detection sites** - ~100ms overhead
6. ✅ **Validate configuration** - Run consistency report before deployment
7. ✅ **Use HTTP-only when possible** - 50-100x faster than browser
8. ✅ **Cache curl-cffi sessions** - Reuse across requests

## References

- **Full Docs:** `docs/ANTIBOT_FRAMEWORK.md`
- **Examples:** `docs/ANTIBOT_EXAMPLES.py`
- **Implementation:** `asagus/layers/antibot_layer*.py`
- **Research:** `antibot.md`

---

**Quick Tip:** Most sites work with `StealthApproach.javascript_shim` + `chrome_124_windows` TLS. Only escalate to Camoufox if getting blocked.
