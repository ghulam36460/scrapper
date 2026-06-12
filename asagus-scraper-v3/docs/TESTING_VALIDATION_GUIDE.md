# ASAGUS v3 Enhancement: Testing & Validation Guide

Quick guide to test and validate all new enhancement modules.

## ✅ Quick Validation Checklist

### 1. Challenge Detector Validation
```python
# backend/test_validators.py

from asagus.layers.challenge_detector import ChallengeDetector

detector = ChallengeDetector(verbose=True)

# Test 1: reCAPTCHA v2
result = detector.detect(
    html='<div class="g-recaptcha" data-sitekey="6Lc_example"></div>',
    status_code=200,
    headers={},
)
assert result["is_challenged"]
assert result["challenges"][0]["type"] == "recaptcha_v2"
print("✓ reCAPTCHA v2 detection works")

# Test 2: Cloudflare
result = detector.detect(
    html='<title>Attention Required!</title>',
    status_code=403,
    headers={"cf-ray": "123-abc"},
)
assert result["severity"] == "high"
print("✓ Cloudflare detection works")

# Test 3: Rate limiting
result = detector.detect(
    html="<html></html>",
    status_code=429,
    headers={"retry-after": "60"},
)
assert result["challenges"][0]["type"] == "http_status"
assert result["challenges"][1]["type"] == "rate_limited"
print("✓ Rate limit detection works")

# Test 4: Normal page (no challenge)
result = detector.detect(
    html="<html><body>Normal page</body></html>",
    status_code=200,
    headers={},
)
assert not result["is_challenged"]
print("✓ Normal page detection works")

print("\n✅ Challenge Detector: PASSED")
```

### 2. Human Behavior Validation
```python
from asagus.layers.human_behavior import WindMouse, HumanBehavior

# Test WindMouse
wind = WindMouse(G_0=9.81, drift=3.5, noise_scale=1.5)

# Test short distance
trajectory_short = wind.calculate_trajectory((0, 0), (50, 50), 300)
assert len(trajectory_short) > 5
assert trajectory_short[0] == (0, 0)
assert abs(trajectory_short[-1][0] - 50) < 1
assert abs(trajectory_short[-1][1] - 50) < 1
print(f"✓ WindMouse short trajectory: {len(trajectory_short)} points")

# Test long distance
trajectory_long = wind.calculate_trajectory((0, 0), (500, 500), 1000)
assert len(trajectory_long) > 50
print(f"✓ WindMouse long trajectory: {len(trajectory_long)} points")

# Test variance in trajectories
trajectory1 = wind.calculate_trajectory((0, 0), (100, 100), 500)
trajectory2 = wind.calculate_trajectory((0, 0), (100, 100), 500)
assert trajectory1 != trajectory2  # Should be slightly different due to randomness
print("✓ WindMouse generates variable trajectories")

# Test HumanBehavior initialization
human = HumanBehavior(typing_variance=0.15, pause_frequency=0.1)
assert human.typing_variance == 0.15
assert human.pause_frequency == 0.1
print("✓ HumanBehavior initialized")

print("\n✅ Human Behavior: PASSED")
```

### 3. GPU Detection Validation
```python
from asagus.layers.compute_accelerator import ComputeAccelerator

# Test detection
accelerator = ComputeAccelerator(allow_gpu=True, allow_tpu=False)
device = accelerator.device

print(f"✓ Detected device: {device}")
assert device in ["cpu", "nvidia_gpu", "amd_gpu", "apple_gpu", "intel_gpu", "tpu"]

config = accelerator.get_config()
assert "capabilities" in config
print(f"✓ Capabilities: {config['capabilities']}")

state = accelerator.state()
assert "device" in state
print("✓ GPU accelerator state retrieved")

print("\n✅ Compute Accelerator: PASSED")
```

### 4. Browser Actions Validation
```python
import asyncio
from asagus.layers.browser_actions import (
    BrowserAction,
    BrowserActionType,
    BrowserActionExecutor,
)

async def test_browser_actions():
    # This is mock test - actual test needs real browser
    
    # Test action creation
    action1 = BrowserAction(
        action=BrowserActionType.navigate,
        url="https://example.com",
        human_like=True,
    )
    assert action1.action == BrowserActionType.navigate
    print("✓ Navigate action created")
    
    action2 = BrowserAction(
        action=BrowserActionType.fill,
        selector="input[name='search']",
        value="test query",
        human_like=True,
    )
    assert action2.selector == "input[name='search']"
    print("✓ Fill action created")
    
    action3 = BrowserAction(
        action=BrowserActionType.extract_text,
        selector=".results",
    )
    assert action3.action == BrowserActionType.extract_text
    print("✓ Extract action created")
    
    print("\n✅ Browser Actions: PASSED")

asyncio.run(test_browser_actions())
```

### 5. Resource Governor Validation
```python
from asagus.layers.resource_governor import ResourceGovernor

governor = ResourceGovernor(
    cpu_workers=4,
    browser_pool_size=10,
    llm_concurrency=5,
    queue_max_size=1000,
)

# Test initial state
assert governor.can_accept_work()
print("✓ Governor accepts work initially")

# Get metrics
metrics = governor.get_metrics()
assert metrics["cpu_workers"] == 4
assert metrics["browser_pool_size"] == 10
assert metrics["llm_concurrency"] == 5
assert metrics["can_accept_work"]
print(f"✓ Metrics: {metrics}")

state = governor.state()
assert "config" in state
assert "metrics" in state
print("✓ Governor state retrieved")

print("\n✅ Resource Governor: PASSED")
```

---

## 🧪 Integration Tests

### Test Against Real Sites (Research Only)

```bash
# 1. Test challenge detection on known challenge sites

# Cloudflare protected:
curl -I https://example-cloudflare-protected.com/

# reCAPTCHA protected:
curl -I https://example-recaptcha-protected.com/

# Normal site:
curl -I https://example.com/
```

### Test Against Detection Benchmarks

```python
# Test against detection sites using Playwright

import asyncio
from playwright.async_api import async_playwright
from asagus.layers.fingerprint_advanced import AdvancedFingerprinting

async def test_fingerprinting():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        
        fingerprinting = AdvancedFingerprinting()
        
        # Visit detection site
        await page.goto("https://browserleaks.com")
        
        # Collect fingerprints
        signals = await fingerprinting.collect_fingerprint_signals(page)
        
        print(f"Canvas fingerprint: {signals['canvas']}")
        print(f"WebGL: {signals['webgl']}")
        print(f"Audio: {signals['audio']}")
        print(f"Entropy score: {signals['entropy_score']}")
        
        await browser.close()

asyncio.run(test_fingerprinting())
```

---

## 📊 Performance Benchmarking

### Measure Detection Accuracy

```python
# Track detection metrics
detection_results = {
    "total_tests": 0,
    "challenges_detected": 0,
    "true_positives": 0,
    "false_positives": 0,
    "false_negatives": 0,
    "accuracy": 0.0,
}

# Test on diverse set of URLs
test_urls = [
    ("https://normal-site.com", False),
    ("https://cloudflare-site.com", True),
    ("https://google.com/search", False),
]

for url, should_have_challenge in test_urls:
    result = detector.detect(html, status, headers)
    detection_results["total_tests"] += 1
    
    if result["is_challenged"] == should_have_challenge:
        detection_results["true_positives"] += 1
    else:
        if result["is_challenged"]:
            detection_results["false_positives"] += 1
        else:
            detection_results["false_negatives"] += 1

detection_results["accuracy"] = (
    detection_results["true_positives"] / detection_results["total_tests"]
)

print(f"Detection Accuracy: {detection_results['accuracy']:.2%}")
```

### Measure Behavior Effectiveness

```python
# Test WindMouse trajectory characteristics
import statistics

durations = []
distances = []

for _ in range(100):
    trajectory = wind.calculate_trajectory((0, 0), (100, 100), 500)
    
    # Measure duration (number of steps)
    durations.append(len(trajectory))
    
    # Measure if trajectory is curved (not straight line)
    # Calculate deviation from straight line
    deviation = 0
    for i, (x, y) in enumerate(trajectory):
        expected_x = i / len(trajectory) * 100
        expected_y = i / len(trajectory) * 100
        deviation += abs(x - expected_x) + abs(y - expected_y)
    
    distances.append(deviation)

print(f"Trajectory variance (steps): {statistics.stdev(durations):.1f}")
print(f"Average deviation from line: {statistics.mean(distances):.1f}")
print(f"✓ Trajectories are curved and variable (bot-resistant)")
```

---

## 🔍 Debugging & Inspection

### Enable Verbose Logging

```python
# In config or at runtime
os.environ["ASAGUS_DEBUG"] = "true"
os.environ["CHALLENGE_DETECTOR_VERBOSE"] = "true"

detector = ChallengeDetector(verbose=True)
```

### Inspect Collected Data

```python
# Save signals for analysis
import json

signals = await fingerprinting.collect_fingerprint_signals(page)

with open("fingerprint_report.json", "w") as f:
    json.dump(signals, f, indent=2)

# Analysis
entropy = signals["entropy_score"]
if entropy > 0.8:
    print("⚠️ High entropy - possibly detectable")
else:
    print("✓ Normal entropy - good stealth")
```

---

## 📈 Continuous Testing

### Set Up Monitoring Dashboard

```python
# API endpoint for monitoring
@app.get("/api/monitoring/enhancements")
async def monitoring():
    return {
        "challenge_detector": {
            "enabled": bool(registry.get_challenge_detector()),
            "state": registry.get_challenge_detector().state(),
        },
        "human_behavior": {
            "enabled": bool(registry.get_human_behavior()),
            "state": registry.get_human_behavior().state(),
        },
        "fingerprinting": {
            "enabled": bool(registry.get_fingerprinting()),
            "state": registry.get_fingerprinting().state(),
        },
        "compute": registry.get_compute_accelerator().state(),
        "resources": registry.get_resource_governor().get_metrics(),
    }
```

### Monitor Over Time

```bash
# Watch metrics in real-time
watch -n 1 'curl -s http://localhost:8000/api/monitoring/enhancements | jq'

# Export metrics to time-series DB
# (Prometheus, InfluxDB, etc.)
```

---

## 🚨 Known Issues & Workarounds

### Issue 1: WindMouse too deterministic
**Solution**: Vary the G_0, drift, and noise_scale parameters
```python
windmouse = WindMouse(
    G_0=random.uniform(8, 12),
    drift=random.uniform(2, 5),
    noise_scale=random.uniform(1, 2)
)
```

### Issue 2: Fingerprints too static
**Solution**: Rotate fingerprints per session
```python
# Change hardware properties between sessions
fingerprint_seed = random.randint(0, 1000000)
```

### Issue 3: Challenge detection too noisy (false positives)
**Solution**: Adjust confidence thresholds
```python
challenge_analysis = detector.detect(html, status, headers)
if challenge_analysis["severity"] in {"high"}:  # Only high severity
    # Manually review
```

---

## ✨ Success Metrics

| Metric | Target | Validation |
|--------|--------|-----------|
| **Challenge Detection Accuracy** | >95% | Compare against ground truth |
| **False Positive Rate** | <5% | Count false alarms |
| **Trajectory Variance** | Std Dev >50 | Check step count variation |
| **Entropy Score** | 0.6-0.9 | Too high/low = suspicious |
| **Response Time** | <500ms | With human behavior |
| **GPU Acceleration** | 5-10x faster | Compare CPU vs GPU OCR |
| **Resource Utilization** | <80% CPU | Monitor during peak load |

---

## 📋 Final Validation Checklist

- [ ] All challenge types detected correctly
- [ ] False positive rate acceptable
- [ ] WindMouse trajectories are variable
- [ ] Human behavior timing is realistic
- [ ] GPU detection working
- [ ] Browser actions execute successfully
- [ ] Resource governor limits enforced
- [ ] Metrics endpoints returning data
- [ ] No crashes or unhandled exceptions
- [ ] Documentation is complete

---

## 🎯 Success Criteria

✅ **If all tests pass**, your enhancement modules are ready for:
1. Staging environment testing
2. Real-world research data collection
3. Effectiveness benchmarking
4. Continuous improvement iteration

---

Run all tests:
```bash
cd backend
python test_validators.py
python -m pytest test_validators.py -v
```

