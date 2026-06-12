# Anti-Bot Evasion Quick Start Guide

## 🚀 Get Started in 5 Minutes

### Step 1: Install Dependencies

```bash
cd asagus-scraper-v3/backend
pip install -r requirements.txt

# Key dependencies:
# - playwright
# - httpx
# - pyyaml
# - curl-cffi (optional but recommended for Layer 3 TLS)
```

### Step 2: Run the Example

```bash
python examples/antibot_complete_example.py
```

This will demonstrate:
- ✓ All 5 detection layers working together
- ✓ Automatic framework selection
- ✓ TLS fingerprinting
- ✓ Browser fingerprint spoofing
- ✓ Behavioral simulation
- ✓ Detection handling

### Step 3: Use in Your Code

```python
import asyncio
import playwright.async_api as pw
from asagus.layers.antibot_orchestrator import create_antibot_orchestrator_from_config

async def scrape_protected_site():
    # Create orchestrator with preset configuration
    orchestrator = create_antibot_orchestrator_from_config(preset="balanced")
    
    # Launch browser
    async with pw.async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        
        # Setup browser context with all anti-bot layers
        context = await orchestrator.setup_browser_context(
            browser,
            url="https://example.com"
        )
        
        page = await context.new_page()
        
        # Navigate to target
        response = await page.goto("https://example.com")
        
        # Handle any detection challenges automatically
        success = await orchestrator.handle_detection_response(
            page, response, url="https://example.com"
        )
        
        if success:
            # Extract data
            title = await page.title()
            content = await page.content()
            print(f"Title: {title}")
            print(f"Content length: {len(content)} bytes")
        
        await browser.close()

# Run
asyncio.run(scrape_protected_site())
```

## 📋 Configuration Presets

Choose the right preset for your use case:

### High Stealth (Maximum Evasion)
```python
orchestrator = create_antibot_orchestrator_from_config(preset="high-stealth")
```
- ★★★ Camoufox binary patches (0% headless detection)
- Full behavioral simulation
- Aggressive adaptive thresholds
- **Use for**: High-security targets (banks, government sites)

### High Speed (Maximum Performance)
```python
orchestrator = create_antibot_orchestrator_from_config(preset="high-speed")
```
- JavaScript-shim stealth only
- No behavioral simulation
- Relaxed adaptive thresholds
- **Use for**: API scraping, low-security targets

### Balanced (Recommended)
```python
orchestrator = create_antibot_orchestrator_from_config(preset="balanced")
```
- ★★ Patchright stealth (67% CreepJS pass)
- Behavioral simulation enabled
- Standard adaptive thresholds
- **Use for**: Most web scraping scenarios

## 🔧 Custom Configuration

### Option 1: YAML File

Create `config/my_config.yaml`:
```yaml
global:
  framework_priority: stealth
  stealth_approach: patchright
  tls_fingerprint: chrome_124_windows
  device_profile: windows_chrome
  enable_behavioral: true

proxies:
  pool:
    - "http://user:pass@proxy1.com:8080"
  rotation_interval: 500

adaptive:
  threshold_light: 3
  threshold_medium: 5
  threshold_heavy: 7
```

Load it:
```python
orchestrator = create_antibot_orchestrator_from_config(
    config_path="config/my_config.yaml"
)
```

### Option 2: Programmatic

```python
from asagus.layers.antibot_orchestrator import AntiBotOrchestrator, AntiBotConfig
from asagus.layers.antibot_layer2_stealth import StealthApproach
from asagus.layers.antibot_layer3_tls import BrowserTLSFingerprint

config = AntiBotConfig(
    framework_priority="stealth",
    stealth_approach=StealthApproach.camoufox,
    tls_fingerprint=BrowserTLSFingerprint.chrome_124_windows,
    device_profile_name="windows_chrome",
    enable_behavioral_simulation=True,
)

orchestrator = AntiBotOrchestrator(config)
```

## 🌐 Add Proxy Pool

```python
proxy_urls = [
    "http://username:password@proxy1.example.com:8080",
    "http://username:password@proxy2.example.com:8080",
]

orchestrator = create_antibot_orchestrator_from_config(
    preset="balanced",
    proxy_urls=proxy_urls
)

# Proxies will automatically:
# ✓ Rotate after 500 requests
# ✓ Verify geolocation matches device timezone
# ✓ Deactivate if response time > 3s
# ✓ Deactivate after 3 consecutive failures
```

## 🤖 CAPTCHA Solving

CAPTCHAs are detected and solved automatically:

```python
# CAPTCHAs are handled in handle_detection_response()
success = await orchestrator.handle_detection_response(page, response, url)

# Supports:
# ✓ reCAPTCHA v2 (requires YOLOv8 model)
# ✓ hCaptcha (requires ML models)
# ✓ Cloudflare Turnstile (PoW simulation)

# Get statistics
stats = orchestrator.captcha_solver.get_solve_statistics()
print(f"CAPTCHA success rate: {stats['success_rate_percent']}%")
```

## 📊 Monitoring & Statistics

### Get Comprehensive Statistics
```python
stats = orchestrator.get_detection_statistics()

# Detection statistics per domain
print(stats["detection_handler"])

# Adaptive mode statistics
print(stats["adaptive_controller"])

# CAPTCHA solving stats
print(stats["captcha_solver"])

# Proxy pool stats
print(stats["proxy_manager"])
```

### Status Report
```python
# Human-readable report
print(orchestrator.get_status_report())
```

### Cross-Layer Consistency
```python
report = orchestrator.get_cross_layer_consistency_report()
print(f"Consistent: {report['consistent']}")
print(f"Warnings: {report['warnings']}")
```

## 🎯 Detection System Coverage

The system automatically handles:

| System | Features | Handled By |
|--------|----------|------------|
| **Cloudflare** | Turnstile, Bot Management | CAPTCHA solver + Layer 5 |
| **DataDome** | ML behavioral analysis | All 5 layers + consistency |
| **Akamai** | JA4+ TLS, HTTP/2 | Layer 3 curl-cffi |
| **PerimeterX** | Behavioral biometrics | Layer 5 sigma log-normal |
| **Imperva** | Device clustering | Profile rotation |
| **Shape** | Advanced ML | All 5 layers |

## 🔄 Adaptive Mode

Detection triggers automatic adaptation:

```
3 detections  → Rotate proxy IP
5 detections  → Rotate device profile
7 detections  → Change stealth approach
100 successes → Reset counter
```

Example:
```python
# System automatically adapts - no code needed!
response = await page.goto("https://protected-site.com")
await orchestrator.handle_detection_response(page, response, url)

# If detected 7 times, stealth approach will automatically change
# from patchright → camoufox → javascript_shim
```

## 🚄 High-Speed HTTP-Only Mode

For API endpoints or server-rendered HTML (10-50x faster):

```python
# Create HTTP client with TLS impersonation
http_client = await orchestrator.create_http_client(
    url="https://api.example.com"
)

# Make request with curl-cffi + Chrome 124 TLS fingerprint
response = await http_client.get("https://api.example.com/data")
print(response.json())

await http_client.aclose()
```

## 🐛 Debugging

Enable detailed logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Now all layer operations will be logged:
# - Framework selection decisions
# - Stealth patches applied
# - TLS fingerprint used
# - Device profile properties
# - Behavioral simulation events
# - Detection events
# - Adaptive actions taken
```

## 📚 Learn More

- **Complete Documentation**: `backend/ANTIBOT_IMPLEMENTATION.md`
- **Configuration Reference**: `backend/config/antibot_config.example.yaml`
- **Research Background**: `antibot.md` (2026 technical monograph)
- **Example Code**: `backend/examples/antibot_complete_example.py`

## 🆘 Common Issues

### Issue: Import errors
**Solution**: Make sure you're in the backend directory
```bash
cd asagus-scraper-v3/backend
export PYTHONPATH=$PWD:$PYTHONPATH
```

### Issue: Playwright not installed
**Solution**: Install Playwright browsers
```bash
playwright install chromium
```

### Issue: curl-cffi not available
**Solution**: Install curl-cffi for TLS impersonation
```bash
pip install curl-cffi
```

### Issue: CAPTCHA not solving
**Solution**: YOLOv8 model is not loaded by default. For production CAPTCHA solving, you need to:
1. Download YOLOv8 model trained on reCAPTCHA
2. Enable with `use_yolov8=True` in CAPTCHA solver initialization

### Issue: Proxies not working
**Solution**: Check proxy URL format: `protocol://username:password@host:port`
```python
# Correct:
"http://user:pass@proxy.example.com:8080"

# Wrong:
"proxy.example.com:8080"  # Missing protocol and credentials
```

## ✅ Verification

Test your setup:

```python
# Run verification script
python examples/antibot_complete_example.py

# Expected output:
# ✓ All 5 layers initialized
# ✓ Browser context created
# ✓ Page loaded successfully
# ✓ Detection handling working
# ✓ Statistics collected
```

## 🎓 Next Steps

1. **Review Documentation**: Read `ANTIBOT_IMPLEMENTATION.md` for complete details
2. **Customize Configuration**: Create your own YAML config file
3. **Add Proxies**: Set up residential proxy pool
4. **Test on Target**: Try against your specific target sites
5. **Monitor Performance**: Use statistics to optimize configuration

## 💡 Pro Tips

1. **Start with "balanced" preset** - works for most scenarios
2. **Use residential proxies** - datacenter IPs trigger detection
3. **Enable behavioral simulation** - especially for DataDome/PerimeterX
4. **Monitor detection statistics** - identify which sites need higher stealth
5. **Use HTTP-only mode when possible** - 10-50x faster for APIs

---

**Ready to scrape?** Run the example and start building! 🚀
