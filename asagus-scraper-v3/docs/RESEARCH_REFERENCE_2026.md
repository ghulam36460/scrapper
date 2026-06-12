# CAPTCHA, Fingerprinting & Bot Evasion Research: Complete GitHub & Algorithm Reference (2026)

This document provides comprehensive research on detection mechanisms, evasion techniques, and powerful algorithms used in the bot detection ecosystem.

---

## Part 1: CAPTCHA & Challenge Systems

### 1.1 Commercial Detection Systems (Most Powerful)

| System | Domain | Strength | Detection Method |
|--------|--------|----------|------------------|
| **reCAPTCHA v3** | Google | Behavioral scoring | Mouse/keyboard/scroll patterns, fingerprinting, TLS analysis |
| **Cloudflare Turnstile** | Cloudflare | Fast, lightweight | Behavioral + device fingerprinting |
| **PerimeterX (px)** | PerimeterX | Very strong | Behavioral biometrics, network analysis, device trust |
| **Akamai Bot Manager** | Akamai | Enterprise-grade | Full HTTP stack analysis + behavioral |
| **Datadome** | Datadome | Very strong | ML-based behavior analysis |
| **Imperva** | Imperva | Strong | Request pattern analysis |
| **AWS WAF** | Amazon | Growing | IP reputation + pattern matching |

### 1.2 Open-Source Detection/Evasion Projects

#### Browser Fingerprinting Libraries

**FingerprintJS** (fingerprintjs/fingerprintjs)
- **Stars**: ~7.5K
- **Language**: TypeScript
- **Purpose**: Generate 99.5% accurate visitor IDs
- **Signals**: Canvas, WebGL, fonts, audio, screen, user agent, timezone
- **URL**: https://github.com/fingerprintjs/fingerprintjs
- **Related**: BotD (Bot Detection) companion - https://botd.fingerprintjs.com

**CreepJS** (abrahamjuliot/creepjs)
- **Stars**: ~2K
- **Language**: Vanilla JS
- **Purpose**: Advanced tampering detection, prototype lies detection
- **Detects**: Spoofed Canvas, WebGL, AudioContext, fake getters
- **URL**: https://github.com/abrahamjuliot/creepjs
- **Demo**: https://abrahamjuliot.github.io/creepjs/

**TinyProfile** (tingxyz/TinyProfile)
- Lightweight fingerprinting (~3KB)
- Fast entropy calculation

**Clientjs** (clientjs/clientjs)
- User agent fingerprinting
- Device metrics

---

## Part 2: Powerful Evasion Frameworks

### 2.1 Anti-Detect Browsers (Most Powerful)

#### **Camoufox** (daijro/camoufox) ⭐⭐⭐
- **Stars**: ~3K+ (growing)
- **Language**: Rust + Python (Firefox fork)
- **Strength**: Deep C++-level spoofing + human behavior
- **Key Features**:
  - Complete Firefox fork with patched detection
  - Randomized hardware specs (realistic market distribution)
  - Human-like mouse movement (ported from HumanCursor)
  - GPU rendering randomization
  - Fake hardware metadata
  - Playwright/Python API
  - Consistent fingerprint via BrowserForge
- **Price**: Free, open-source
- **URL**: https://github.com/daijro/camoufox
- **Research Value**: Study C++ patching techniques, detection bypass patterns

#### **undetected-chromedriver** (ultrafunkamsterdam/undetected-chromedriver)
- **Stars**: ~9K+
- **Language**: Python
- **Strength**: CDP modification + stealth patches
- **How it works**: Removes headless mode detection, patches DevTools Protocol
- **Limitations**: Detectable by advanced behavioral analysis
- **URL**: https://github.com/ultrafunkamsterdam/undetected-chromedriver

#### **Browser.sh** (goto-bus-stop/browser.sh)
- Bash-based browser fingerprinting test

#### **itbrowser-net/undetectable-fingerprint-browser**
- Multilogin-like spoofing

---

### 2.2 Puppeteer & Playwright Stealth Patches

#### **puppeteer-extra** (berstend/puppeteer-extra)
- **Stars**: ~4K+
- **Language**: JavaScript
- **Plugins**: stealth, block-resources, extra-stealth
- **URL**: https://github.com/berstend/puppeteer-extra
- **Research Value**: Collection of evasion techniques + plugin architecture

#### **Playwright Extra** (playwright-extra)
- Similar ecosystem for Playwright
- Stealth plugins
- Resource blocking

---

### 2.3 Human-Like Behavior Simulation (Key for Research)

#### **HumanCursor** (riflosnake/HumanCursor) ⭐⭐
- **Stars**: ~1.5K
- **Language**: Python (with JS port)
- **Purpose**: Realistic human mouse movement
- **Algorithm**: Motion dynamics with variable speed/acceleration/curvature
- **Features**:
  - Natural motion curves (not straight lines)
  - Variable speed + acceleration
  - Momentum-like movement
  - Supports clicks, drags
  - Web + system cursor modes
  - Integrates with Selenium/Playwright
- **URL**: https://github.com/riflosnake/HumanCursor
- **Installation**: `pip install HumanCursor`
- **Research Value**: Study natural motion patterns, ML training data

#### **WindMouse Algorithm** (AsfhtgkDavid/windmouse) ⭐⭐⭐
- **Stars**: ~500 (seminal work)
- **Language**: Python + ports to JS, Go, Rust
- **Physics-based approach**:
  - Simulates gravity + wind forces
  - Natural trajectory generation
  - Parametrizable physics (G_0, drift, noise)
  - Used in many bot frameworks
- **How it works**:
  ```
  trajectory = simulated using F=ma
  with gravity pulling toward target
  and random wind creating curves
  ```
- **URL**: https://github.com/AsfhtgkDavid/windmouse
- **Ports**: 
  - JavaScript: arevi/wind-mouse
  - Go: go-rod/rod (has WindMouse impl)
- **Research Value**: Foundational algorithm for behavioral evasion

#### **ghost-cursor** (Xetera/ghost-cursor)
- **Language**: TypeScript
- **Bezier curve mouse movement for Puppeteer**
- **URL**: https://github.com/Xetera/ghost-cursor

#### **fake-browser** (kkoooqk/fake-browser)
- Complete fake browser fingerprinting
- User-agent + device spoofing

#### **bezier-easing** (gre/bezier-easing)
- Easing functions for smooth curves

---

### 2.4 Keystroke Dynamics & Typing Behavior

#### **keystroke-dynamics** research
- Dwell time (key down to key up)
- Flight time (key up to next key down)
- Digraph analysis (interval between specific key pairs)
- **Defense**: Randomize within human ranges

Papers:
- "Keystroke Dynamics as a Biometric for Authentication" - ACM
- PerimeterX keyboard analysis papers

---

### 2.5 CAPTCHA Solving Services (Research Reference)

**Commercial APIs** (for integration research):
- **CapSolver** (capsolver.com) - Modern, supports reCAPTCHA v3, Turnstile
- **2Captcha** (2captcha.com) - Legacy, extensive doc
- **Anti-Captcha** (anti-captcha.com) - Various CAPTCHA types
- **DeathByCaptcha** - Legacy service
- **Solver.com** - Slider CAPTCHAs

**Open-Source Solving**:
- **Buster** (dessant/buster) - Speech recognition for audio CAPTCHA
- **darknet/YOLO** - Image detection for visual CAPTCHAs
- **PaddleOCR** (PaddlePaddle/PaddleOCR) - GPU-accelerated OCR
- **EasyOCR** (JaidedAI/EasyOCR) - Multi-language OCR
- **Tesseract** - Classic OCR

---

## Part 3: TLS/HTTP Fingerprinting Evasion

### 3.1 TLS Fingerprinting (Critical for Advanced Detection)

Modern anti-bots analyze:
- **JA3 fingerprint**: TLS version, ciphers, curves
- **HTTP/2 fingerprint**: Header order, pseudo-headers
- **TLS 1.3 fingerprints**: Key shares, supported versions

#### **curl-impersonate** (lwthiker/curl-impersonate) ⭐⭐⭐
- **Purpose**: Impersonate browser TLS signatures
- **Languages**: C (libcurl fork) + Python wrapper
- **How it works**: Modifies TLS parameters to match Chrome/Firefox/Safari exactly
- **Supported**: Chrome, Firefox, Safari, Edge
- **URL**: https://github.com/lwthiker/curl-impersonate
- **Python wrapper**: piaoliang/curl-impersonate-python
- **Research Value**: Deep TLS fingerprint analysis + evasion

#### **python-tls-client** (dleemiller/python-tls-client)
- **Purpose**: Custom TLS fingerprints in Python
- **URL**: https://github.com/dleemiller/python-tls-client

#### **CycleTLS** (norbertogomez/cycleTLS)
- Go + JS + Python bindings
- TLS fingerprint cycling
- Works with Puppeteer

#### **JA3 Tools**
- **ja3** (salesforce/ja3) - Generate JA3 fingerprints
- **JA3 Fingerprints DB** - Catalog of browser fingerprints
- **Fingerprint bypass** via TLS parameter randomization

---

## Part 4: Detection Benchmarking Tools (Test Your Evasion)

### 4.1 Online Testing Platforms

| Tool | URL | What It Tests |
|------|-----|---------------|
| **BrowserLeaks** | https://browserleaks.com | Canvas, WebGL, AudioContext, fonts, IP leak, WebRTC |
| **Pixelscan** | https://pixelscan.net | Advanced detection (PerimeterX-like) |
| **CreepJS Demo** | https://abrahamjuliot.github.io/creepjs | Tampering, prototype lies |
| **botd.fingerprint.com** | https://botd.fingerprintjs.com | Bot likelihood score |
| **browserspy.dk** | https://www.browserspy.dk | Detailed browser properties |
| **ipleak.net** | https://ipleak.net | WebRTC IP leak |
| **canvasblocker.com** | Canvas fingerprint test |
| **devicepx.com** | Device fingerprint demo |

### 4.2 Open-Source Testing Tools

**Playwright Inspector** (Playwright built-in)
- `playwright open` - Visual debugging
- Protocol monitoring

**Puppeteer DevTools** 
- Chrome DevTools Protocol inspection

**Chromium Tracing**
- `--enable-features=NetworkService --log-net-log=net.json`

---

## Part 5: Advanced Algorithms & Techniques

### 5.1 Behavioral Biometrics Evasion

#### Mouse Movement
- **Linear bad** ❌ - Detected as bot
- **WindMouse** ✅ - Physics-based curves
- **Bezier curves** ✅ - Smooth mathematical curves
- **Perlin noise** ✅ - Natural randomness

#### Typing Pattern
```python
# Research-backed human ranges:
- Dwell time (key down): 100-200ms
- Flight time (between keys): 50-150ms
- Digraph variance: ±20-30% around mean
- Occasional backspace corrections: 5-10% of typing
- Pause frequency: 5-15% (thinking)
```

#### Scroll Behavior
- Smooth acceleration
- Variable speed
- Occasional pauses
- Direction changes with reading

#### Mouse Jitter
- Micro-movements while idle
- Natural tremor (~5-10 pixels)
- Variable amplitude

### 5.2 Fingerprint Randomization (Market-Share Distribution)

**Real-world statistics** (use for realistic spoofing):

```json
{
  "os": {
    "Windows": 0.75,
    "macOS": 0.15,
    "Linux": 0.10
  },
  "browser": {
    "Chrome": 0.65,
    "Safari": 0.20,
    "Firefox": 0.10,
    "Edge": 0.05
  },
  "screen_resolution": [
    "1920x1080": 0.30,
    "1366x768": 0.20,
    "1440x900": 0.15,
    ...
  ]
}
```

**BrowserForge** (in Camoufox) uses real Chrome user-agent distribution stats.

### 5.3 Machine Learning Approaches

#### Anomaly Detection Evasion
- Train GAN to generate human-like mouse trajectories
- Reinforcement Learning for optimal behavior patterns
- Autoencoder for realistic fingerprint combinations

**Papers**:
- "Adversarial Examples Against Deep Neural Networks for Malware Classification" - 2016
- "GAN-based Bot Detection" (proprietary research)

---

## Part 6: Open-Source Projects by Category

### Anti-Bot Frameworks
- **Camoufox**: Firefox + evasion (Rust)
- **undetected-chromedriver**: CDP patching (Python)
- **puppeteer-extra**: Plugin system (Node.js)

### Fingerprinting
- **FingerprintJS**: Client-side (TS)
- **CreepJS**: Detection testing (JS)
- **python-tls-client**: TLS fingerprinting (Python)

### Behavior Simulation
- **HumanCursor**: Mouse movement (Python)
- **WindMouse**: Physics algorithm (Python)
- **ghost-cursor**: Bezier curves (TS)

### OCR/CAPTCHA Solving
- **PaddleOCR**: GPU OCR (Python)
- **EasyOCR**: Multi-language OCR (Python)
- **Tesseract**: Classic OCR (C++)

### Testing & Benchmarking
- **OWASP ZAP**: Security testing
- **Burp Suite Community**: Web proxy
- **Playwright Inspector**: Built-in debugging

---

## Part 7: Recommended Research Roadmap

### Phase 1: Understanding Detection (Week 1-2)
1. **Fingerprinting Research**
   - Study FingerprintJS source code
   - Test on BrowserLeaks
   - Understand Canvas/WebGL/AudioContext analysis
   
2. **Behavioral Analysis**
   - Read PerimeterX/Datadome white papers
   - Analyze mouse patterns in CreepJS
   - Study TLS fingerprinting

### Phase 2: Evasion Implementation (Week 3-4)
1. **Basic Evasion**
   - Implement WindMouse algorithm
   - Add HumanCursor integration
   - Randomize basic fingerprints

2. **Challenge Detection**
   - Pattern matching (implemented)
   - Header analysis (implemented)
   - Response classification

### Phase 3: Advanced Techniques (Week 5-6)
1. **TLS Evasion**
   - Integrate curl-impersonate or python-tls-client
   - Analyze JA3 fingerprints
   - Test against advanced detectors

2. **GPU-Accelerated CAPTCHA**
   - Integrate PaddleOCR
   - Benchmark solving speed
   - Compare with API services

### Phase 4: Comprehensive Testing (Week 7-8)
1. **Benchmark Testing**
   - Test against all major detection systems
   - Collect metrics on effectiveness
   - Document detection/evasion gaps

2. **ML-Based Improvements**
   - Train model on successful patterns
   - Anomaly detection
   - Continuous improvement loop

---

## Part 8: GitHub Resources by Topic

### Essential Reading (Stars/Forks)

| Repository | Stars | Topic | Why Study |
|------------|-------|-------|-----------|
| daijro/camoufox | 3K+ | Anti-detect | Deep evasion techniques |
| fingerprint js/fingerprintjs | 7.5K | Detection | Understand signals |
| abrahamjuliot/creepjs | 2K | Detection Testing | Tampering detection |
| ultrafunkamsterdam/undetected-chromedriver | 9K | Chrome patching | CDP modification |
| berstend/puppeteer-extra | 4K | Plugin system | Modular evasion |
| riflosnake/HumanCursor | 1.5K | Behavior | Mouse movement |
| AsfhtgkDavid/windmouse | 500 | Algorithm | Physics-based motion |
| lwthiker/curl-impersonate | 2K | TLS | Advanced fingerprinting |
| PaddlePaddle/PaddleOCR | 40K | OCR | GPU-accelerated |
| JaidedAI/EasyOCR | 22K | OCR | Simple + powerful |

### Collections/Curated Lists

- **TheGP/Everything-About-Captchas**: Comprehensive CAPTCHA research
- **TheGP/untidetect-tools**: Curated anti-detect browsers list
- **inteltechnologies/bot-detection-prevention**: Research compilation

---

## Part 9: Implementation Priorities by Research Goal

### Goal: Understand CAPTCHA Mechanisms
1. Implement challenge detector ✅
2. Integrate CreepJS for tampering detection
3. Collect signals from target sites
4. Analyze pattern correlations

### Goal: Develop Anti-Bot Library
1. Implement HumanBehavior ✅
2. Implement AdvancedFingerprinting ✅
3. Add TLS fingerprinting (curl-impersonate)
4. Create composite detection system

### Goal: Test Evasion Effectiveness
1. Deploy Camoufox fork or patches
2. Run against BrowserLeaks, Pixelscan
3. Test against production anti-bots
4. Document detection gaps

### Goal: GPU-Accelerated CAPTCHA Solving
1. Integrate PaddleOCR ✅
2. Benchmark vs API services
3. Implement model selection logic
4. Optimize batch processing

---

## Part 10: Key Research Papers & Whitepapers

### Academic Research
- "Cookies That Give You Away: The Privacy Impact of Web Cookies" - USENIX
- "The Most Dangerous Code in the Browser" - Google
- "Detecting Automated Browser Activity" - PerimeterX whitepaper
- "Behavioral Biometrics for Fraud Detection" - Datadome

### Security Conferences
- OWASP Top 10 - Bot Management section
- Black Hat - Browser security talks
- DEF CON - Web scraping vs anti-scraping

---

## Part 11: Running Your Research Safely

### Environment Setup
```bash
# Research VM recommended
# Linux (avoid Windows detection patterns)
# Fresh OS profile for each test
# Isolated network (no personal data)
# Temporary storage only

pip install playwright puppeteer-stealth easyocr sentence-transformers

# Optional GPU support
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

### Data Collection Framework
```python
# Log all signals for analysis
# Challenge types detected
# Evasion technique effectiveness
# False positive/negative rates
# Response time metrics
# Fingerprint entropy scores
```

### Benchmarking Script Example
```python
import asyncio
from asagus.layers.challenge_detector import ChallengeDetector
from asagus.layers.human_behavior import HumanBehavior

async def benchmark():
    # 1. Test against sample sites
    # 2. Collect metrics
    # 3. Compare techniques
    # 4. Document findings
    pass
```

---

## Conclusion

This ecosystem represents the state-of-the-art in bot detection/evasion research. Key insights:

1. **Detection is evolving faster than evasion** - Modern systems use ML + behavioral analysis
2. **Deep-level patching > JS-level spoofing** - C++ modifications beat JavaScript tricks
3. **Fingerprint consistency matters** - Randomizing too much = detection
4. **Human-like behavior is key** - Mouse/keyboard/scroll patterns reveal bots
5. **TLS matters** - Network-level fingerprints increasingly analyzed
6. **GPU acceleration is valuable** - For solving and ML analysis

---

**For Maximum Learning**: Study Camoufox source code, run against detection benchmarks, compare effectiveness metrics, document your findings.

