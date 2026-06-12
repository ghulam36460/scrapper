# ASAGUS v3 Enhancement: Quick Start Implementation Guide

This guide shows how to integrate the new powerful enhancement modules into your existing ASAGUS scraper.

## 🚀 Step 1: Install Additional Dependencies

Add to `backend/requirements.txt`:

```
# CAPTCHA & Challenge Handling
# (Built-in detection, solving via APIs)

# Human-like Behavior & Mouse Simulation
# (Pure Python, no additional dependencies beyond playwright)

# Advanced Fingerprinting
# (Built-in JavaScript evaluation)

# GPU/TPU Support (Optional - only if you want GPU acceleration)
# Uncomment as needed:
# torch>=2.0.0  # with CUDA: pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
# tensorflow>=2.13.0  # with CUDA support
# paddleocr>=2.7.0  # For GPU-accelerated OCR
# easyocr>=1.7.0  # For GPU-accelerated OCR

# TLS/HTTP Fingerprinting (Optional)
# python-tls-client>=0.2.0  # Advanced TLS fingerprint evasion
```

Then install:
```bash
cd backend
pip install -r requirements.txt
```

## 🔧 Step 2: Update Backend Config

Modify `asagus/config.py` to add new settings:

```python
from pydantic import Field

class Settings(BaseSettings):
    # ... existing settings ...
    
    # ===== NEW: Deep Agent Mode =====
    enable_deep_agent_mode: bool = Field(default=False, description="Enable Deep Agent Mode")
    browser_action_budget: int = Field(default=20, description="Max actions per browser workflow")
    deep_agent_manual_review_on_challenge: bool = Field(default=True)
    
    # ===== NEW: Human-like Behavior =====
    enable_human_behavior_simulation: bool = Field(default=True)
    human_typing_variance: float = Field(default=0.15)
    human_pause_frequency: float = Field(default=0.10)
    
    # ===== NEW: Challenge Detection =====
    enable_challenge_detection: bool = Field(default=True)
    challenge_detection_verbose: bool = Field(default=False)
    
    # ===== NEW: GPU/TPU =====
    enable_gpu_acceleration: bool = Field(default=True)
    enable_tpu_acceleration: bool = Field(default=False)
    gpu_ocr_model: str = Field(default="paddleocr")  # or "easyocr"
    
    # ===== NEW: Advanced Fingerprinting =====
    enable_advanced_fingerprinting: bool = Field(default=True)
    
    # ===== NEW: Resource Governance =====
    cpu_worker_processes: int = Field(default=4, ge=1, le=128)
    browser_pool_size: int = Field(default=10, ge=0, le=50)
    llm_concurrency: int = Field(default=5, ge=1, le=50)
    pipeline_queue_maxsize: int = Field(default=5000, ge=100, le=100000)
```

## 📝 Step 3: Initialize Components in Main Application

Create or update `asagus/layers/registry.py`:

```python
"""Layer registry for easy access to all enhancement modules."""

from asagus.layers.challenge_detector import ChallengeDetector
from asagus.layers.human_behavior import HumanBehavior
from asagus.layers.fingerprint_advanced import AdvancedFingerprinting
from asagus.layers.compute_accelerator import ComputeAccelerator
from asagus.layers.browser_actions import BrowserActionExecutor
from asagus.layers.resource_governor import ResourceGovernor
from asagus.config import get_settings


class LayerRegistry:
    """Central registry for all scraper enhancement layers."""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        settings = get_settings()
        
        # Challenge Detection
        self.challenge_detector = (
            ChallengeDetector(verbose=settings.challenge_detection_verbose)
            if settings.enable_challenge_detection
            else None
        )
        
        # Human-like Behavior
        self.human_behavior = (
            HumanBehavior(
                typing_variance=settings.human_typing_variance,
                pause_frequency=settings.human_pause_frequency,
            )
            if settings.enable_human_behavior_simulation
            else None
        )
        
        # Advanced Fingerprinting
        self.fingerprinting = (
            AdvancedFingerprinting()
            if settings.enable_advanced_fingerprinting
            else None
        )
        
        # GPU/TPU Acceleration
        self.compute = ComputeAccelerator(
            allow_gpu=settings.enable_gpu_acceleration,
            allow_tpu=settings.enable_tpu_acceleration,
        )
        
        # Resource Governor
        self.resource_governor = ResourceGovernor(
            cpu_workers=settings.cpu_worker_processes,
            browser_pool_size=settings.browser_pool_size,
            llm_concurrency=settings.llm_concurrency,
            queue_max_size=settings.pipeline_queue_maxsize,
        )
    
    def get_challenge_detector(self):
        return self.challenge_detector
    
    def get_human_behavior(self):
        return self.human_behavior
    
    def get_fingerprinting(self):
        return self.fingerprinting
    
    def get_compute_accelerator(self):
        return self.compute
    
    def get_resource_governor(self):
        return self.resource_governor


# Global singleton instance
registry = LayerRegistry()
```

## 🎯 Step 4: Integrate into Fetch Pipeline

Update `asagus/layers/fetch.py`:

```python
"""Example integration of enhancement modules."""

from asagus.layers.registry import registry
from asagus.models import FetchResult


async def fetch_with_enhancements(url: str, proxy_url: str = "") -> dict:
    """Fetch with challenge detection and enhanced analysis."""
    
    # 1. Fetch the page
    fetch_result = await fetch_page(url, proxy_url)
    
    # 2. Detect challenges
    if registry.get_challenge_detector():
        challenge_analysis = registry.get_challenge_detector().detect(
            html=fetch_result.body or "",
            status_code=fetch_result.status_code or 200,
            headers=fetch_result.response_headers or {},
            final_url=fetch_result.final_url,
        )
        
        if challenge_analysis["severity"] in {"high", "block"}:
            return {
                "status": "challenge_detected",
                "challenge_analysis": challenge_analysis,
                "requires_manual_review": True,
                "recommendation": challenge_analysis["recommendation"],
            }
    
    # 3. Collect fingerprints for research (don't slow down normal fetch)
    fingerprint_data = None
    if registry.get_fingerprinting():
        # Only collect if we have a Playwright page context
        # This would be called in deep_agent_mode
        pass
    
    return {
        "status": "success",
        "fetch": fetch_result,
        "challenge_analysis": challenge_analysis if registry.get_challenge_detector() else None,
    }
```

## 🤖 Step 5: Example - Deep Agent Mode Workflow

Create `asagus/layers/workflows.py`:

```python
"""Predefined browser action workflows for research."""

from asagus.layers.browser_actions import BrowserAction, BrowserActionType


def restaurant_search_workflow(search_query: str, target_url: str) -> list[BrowserAction]:
    """Workflow to search for restaurants and extract data."""
    return [
        BrowserAction(
            action=BrowserActionType.navigate,
            url=target_url,
            human_like=True,
        ),
        BrowserAction(
            action=BrowserActionType.wait_for_selector,
            selector="input[type='search']",
            timeout_ms=10000,
            human_like=True,
        ),
        BrowserAction(
            action=BrowserActionType.fill,
            selector="input[type='search']",
            value=search_query,
            human_like=True,
        ),
        BrowserAction(
            action=BrowserActionType.human_pause,
            duration_ms=random.randint(300, 800),
        ),
        BrowserAction(
            action=BrowserActionType.click,
            selector="button[type='submit']",
            human_like=True,
        ),
        BrowserAction(
            action=BrowserActionType.wait_for_selector,
            selector=".result-item",
            timeout_ms=15000,
        ),
        BrowserAction(
            action=BrowserActionType.extract_text,
            selector=".result-item",
        ),
    ]


def captcha_detection_workflow(url: str) -> list[BrowserAction]:
    """Workflow to visit page and detect challenges."""
    return [
        BrowserAction(
            action=BrowserActionType.navigate,
            url=url,
            human_like=True,
        ),
        BrowserAction(
            action=BrowserActionType.wait_for_selector,
            selector="body",
            timeout_ms=10000,
        ),
        BrowserAction(
            action=BrowserActionType.screenshot,
            value="/tmp/page_screenshot.png",
        ),
        BrowserAction(
            action=BrowserActionType.evaluate_js,
            code="() => ({ title: document.title, url: window.location.href })",
        ),
    ]
```

## 📊 Step 6: Expose Metrics Endpoint

Add to FastAPI app:

```python
from fastapi import FastAPI
from asagus.layers.registry import registry

app = FastAPI()

@app.get("/api/system/enhancements")
async def get_enhancements_status():
    """Check status of all enhancement modules."""
    return {
        "challenge_detector": registry.get_challenge_detector().state() if registry.get_challenge_detector() else None,
        "human_behavior": registry.get_human_behavior().state() if registry.get_human_behavior() else None,
        "fingerprinting": registry.get_fingerprinting().state() if registry.get_fingerprinting() else None,
        "compute_accelerator": registry.get_compute_accelerator().state(),
        "resource_governor": registry.get_resource_governor().get_metrics(),
    }

@app.get("/api/system/resources")
async def get_resource_metrics():
    """Get real-time resource utilization."""
    return registry.get_resource_governor().get_metrics()
```

## 🧪 Step 7: Testing

Create `backend/test_enhancements.py`:

```python
"""Test new enhancement modules."""

import asyncio
from asagus.layers.challenge_detector import ChallengeDetector


def test_challenge_detector():
    detector = ChallengeDetector(verbose=True)
    
    # Test reCAPTCHA v2 detection
    html_recaptcha = '<div class="g-recaptcha" data-sitekey="123"></div>'
    result = detector.detect(html_recaptcha, 200, {})
    assert result["is_challenged"]
    assert "recaptcha_v2" in [c["type"] for c in result["challenges"]]
    print("✓ reCAPTCHA v2 detection works")
    
    # Test Cloudflare challenge detection
    html_cf = '<title>Attention Required!</title>'
    result = detector.detect(html_cf, 403, {"cf-ray": "123abc"})
    assert result["severity"] == "high"
    print("✓ Cloudflare challenge detection works")
    
    # Test rate limiting
    html_normal = "<html><body>Normal page</body></html>"
    result = detector.detect(html_normal, 429, {"retry-after": "60"})
    assert result["severity"] == "medium"
    print("✓ Rate limit detection works")


def test_human_behavior():
    from asagus.layers.human_behavior import HumanBehavior, WindMouse
    
    wind = WindMouse()
    trajectory = wind.calculate_trajectory((0, 0), (100, 100), 500)
    assert len(trajectory) > 0
    assert trajectory[0] == (0, 0)
    assert trajectory[-1] == (100, 100)
    print(f"✓ WindMouse trajectory generated: {len(trajectory)} points")
    
    human = HumanBehavior()
    assert human.state()["algorithms"] == ["windmouse_physics", "human_typing_variance", "scroll_smoothing"]
    print("✓ HumanBehavior initialized successfully")


def test_gpu_detection():
    from asagus.layers.compute_accelerator import ComputeAccelerator
    
    accelerator = ComputeAccelerator(allow_gpu=True, allow_tpu=False)
    config = accelerator.get_config()
    print(f"✓ Detected device: {accelerator.device}")
    print(f"✓ GPU capabilities: {config['capabilities']}")


if __name__ == "__main__":
    print("Testing ASAGUS Enhancements...\n")
    test_challenge_detector()
    print()
    test_human_behavior()
    print()
    test_gpu_detection()
    print("\n✅ All tests passed!")
```

Run tests:
```bash
cd backend
python -m pytest test_enhancements.py -v
# or
python test_enhancements.py
```

## 📈 Step 8: Monitor and Research

**Check enhancement status**:
```bash
curl http://localhost:8000/api/system/enhancements
curl http://localhost:8000/api/system/resources
```

**Analyze detection effectiveness**:
- Test against: https://browserleaks.com, https://pixelscan.net
- Monitor challenge detection accuracy
- Track human-like behavior effectiveness
- Measure GPU acceleration impact

## 🔍 Key Research Insights to Collect

1. **Challenge Detection Accuracy**
   - Log all detected challenges
   - Compare against ground truth
   - Refine patterns based on false positives

2. **Fingerprint Uniqueness**
   - Compare entropy scores
   - Identify high-entropy signals
   - Test fingerprint rotation strategies

3. **Behavioral Pattern Recognition**
   - Monitor which mouse patterns trigger detection
   - Test typing speed ranges
   - Analyze scroll behavior effectiveness

4. **GPU/TPU Acceleration**
   - Measure OCR solving time
   - Compare against API-based services
   - Benchmark embedding generation

## 🚨 Important Notes

✅ **Allowed for Research**:
- Challenge detection (no bypass)
- Fingerprint collection
- Human-like behavior simulation
- CAPTCHA solving algorithms
- Anti-bot mechanism analysis

❌ **NOT Allowed**:
- Credential theft
- Platform ToS violations
- Unauthorized access
- Social platform automation

---

**Next Steps**:
1. Run test suite
2. Deploy to staging
3. Monitor effectiveness
4. Collect research data
5. Iterate on algorithms
6. Document findings

