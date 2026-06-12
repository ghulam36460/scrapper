# ASAGUS v3 Enhancement Guide: Making It Maximally Powerful for CAPTCHA/Bot Research (2026)

**Context**: You're building this scraper to analyze and understand how CAPTCHAs, anti-bot systems, and fingerprinting work—so you can develop robust anti-bot/anti-scraping libraries. The following enhancements are research-focused, educational, and legitimate for security analysis.

---

## Part 1: CAPTCHA & Challenge Detection (Tier 1 - Highest Impact)

### 1.1 Challenge Detector Module

Modern anti-bots (reCAPTCHA v3, Cloudflare Turnstile, Akamai, PerimeterX) use:
- **Page redirect** to challenge page
- **JavaScript insertion** (invisible challenge)
- **Status codes** (403, 429, 503)
- **Response headers** (challenge tokens, refresh-after, etc.)
- **DOM markers** (specific divs, iframes for challenge widgets)
- **HTTP-only cookies** (challenge tokens)

**Implementation**:

Create `asagus/layers/challenge_detector.py`:

```python
import re
from enum import Enum
from typing import Optional
from asagus.models import FetchResult, utc_now


class ChallengeType(str, Enum):
    recaptcha_v2 = "recaptcha_v2"
    recaptcha_v3 = "recaptcha_v3"
    cloudflare_turnstile = "cloudflare_turnstile"
    cloudflare_challenge = "cloudflare_challenge"
    akamai_bot_manager = "akamai_bot_manager"
    perimeter_x = "perimeter_x"
    datadome = "datadome"
    imperva = "imperva"
    unknown_challenge = "unknown_challenge"


class ChallengeDetector:
    """Detects bot challenges, rate limiting, and access blocks."""

    # Patterns for challenge detection
    CAPTCHA_PATTERNS = {
        ChallengeType.recaptcha_v2: [
            r'g-recaptcha(?!-enterprise)',
            r"grecaptcha\.render",
            r'data-sitekey="[^"]+"',
        ],
        ChallengeType.recaptcha_v3: [
            r'g-recaptcha-enterprise',
            r"grecaptcha\.enterprise",
        ],
        ChallengeType.cloudflare_turnstile: [
            r'Cloudflare Turnstile',
            r'cf_clearance',
            r'window\.turnstile',
        ],
        ChallengeType.cloudflare_challenge: [
            r'<title>Attention Required!',
            r'Cloudflare',
            r'Checking your browser before accessing',
            r'__cf_bm',
        ],
        ChallengeType.akamai_bot_manager: [
            r"akamai\.require",
            r"_bm\.js",
            r"sen\.js",
        ],
        ChallengeType.perimeter_x: [
            r"/_px\.js",
            r"px\.js",
            r"PXScript",
        ],
        ChallengeType.datadome: [
            r"dd_js",
            r"datadome",
        ],
        ChallengeType.imperva: [
            r"imspx\.js",
            r"_Incapsula_Resource",
        ],
    }

    def __init__(self, verbose: bool = False):
        self.verbose = verbose

    def detect(self, fetch: FetchResult) -> dict[str, object]:
        """Analyze fetch result for challenges."""
        challenges = []
        html = fetch.body or ""
        headers = fetch.response_headers or {}
        status = fetch.status_code or 0

        # 1. Check status codes
        if status in {403, 429, 503}:
            challenges.append({
                "type": "http_status",
                "status_code": status,
                "message": self._status_message(status),
            })

        # 2. Check headers
        header_challenges = self._check_headers(headers)
        challenges.extend(header_challenges)

        # 3. Check HTML patterns
        detected_types = self._detect_html_patterns(html)
        for ctype, patterns in detected_types.items():
            challenges.append({
                "type": ctype.value,
                "detected_patterns": patterns,
                "confidence": len(patterns) / len(self.CAPTCHA_PATTERNS[ctype]),
            })

        # 4. Check redirect logic
        if self._is_redirect_page(html, fetch.final_url):
            challenges.append({
                "type": "redirect",
                "message": "Page appears to be a challenge redirect",
            })

        # 5. Check frame/iframe injection
        if self._has_challenge_frames(html):
            challenges.append({
                "type": "challenge_frame_detected",
                "message": "Challenge widget iframe detected",
            })

        is_challenged = bool(challenges)
        severity = self._calculate_severity(challenges)

        return {
            "timestamp": utc_now().isoformat(),
            "url": fetch.final_url,
            "status_code": status,
            "is_challenged": is_challenged,
            "severity": severity,  # "low", "medium", "high", "block"
            "challenges": challenges,
            "recommendation": self._recommend_action(challenges, severity),
        }

    def _detect_html_patterns(self, html: str) -> dict[ChallengeType, list[str]]:
        """Detect CAPTCHA and bot challenge patterns in HTML."""
        detected = {}
        for ctype, patterns in self.CAPTCHA_PATTERNS.items():
            matches = []
            for pattern in patterns:
                if re.search(pattern, html, re.IGNORECASE):
                    matches.append(pattern[:50])
            if matches:
                detected[ctype] = matches
        return detected

    def _check_headers(self, headers: dict) -> list[dict]:
        """Check response headers for challenge indicators."""
        challenges = []
        headers_lower = {k.lower(): v for k, v in headers.items()}

        if "cf_ray" in headers_lower or "cf-ray" in headers_lower:
            challenges.append({
                "type": "cloudflare_signature",
                "header": "CF-Ray",
                "confidence": 0.8,
            })

        if "x-challenge" in headers_lower:
            challenges.append({
                "type": "generic_challenge_header",
                "header": "X-Challenge",
                "confidence": 0.7,
            })

        # Check for refresh/retry directives
        if "retry-after" in headers_lower:
            challenges.append({
                "type": "rate_limited",
                "header": "Retry-After",
                "message": f"Rate limit detected: {headers_lower['retry-after']}",
            })

        return challenges

    def _is_redirect_page(self, html: str, url: str) -> bool:
        """Check if page is a redirect/challenge page."""
        redirect_keywords = [
            "Checking your browser",
            "Please wait while we check",
            "temporarily unavailable",
            "security check",
            "verify you",
            "challenge",
            "access denied",
        ]

        html_lower = html.lower()
        title_match = re.search(r"<title[^>]*>([^<]+)</title>", html, re.I)
        if title_match:
            title = title_match.group(1).lower()
            for keyword in redirect_keywords:
                if keyword in title:
                    return True

        for keyword in redirect_keywords:
            if keyword in html_lower:
                return True

        return False

    def _has_challenge_frames(self, html: str) -> bool:
        """Detect challenge widget iframes/frames."""
        challenge_domains = [
            "recaptcha",
            "challenges.cloudflare",
            "cdn.cookielaw",
            "_challenge",
            "akamai",
        ]
        for domain in challenge_domains:
            if domain.lower() in html.lower():
                return True
        return False

    def _calculate_severity(self, challenges: list[dict]) -> str:
        """Determine severity of challenge."""
        if not challenges:
            return "none"

        has_high = any(c.get("type") in {
            "recaptcha_v2", "recaptcha_v3", "cloudflare_challenge"
        } for c in challenges)

        has_rate_limit = any("rate_limit" in c.get("type", "") for c in challenges)
        has_block = any(c.get("status_code") in {403, 429} for c in challenges)

        if has_high:
            return "high"
        if has_block:
            return "high"
        if has_rate_limit:
            return "medium"

        return "low"

    def _recommend_action(self, challenges: list, severity: str) -> str:
        """Recommend next action."""
        if severity == "high":
            return "manual_review_required"
        if severity == "medium":
            return "wait_and_retry"
        return "proceed"

    def _status_message(self, status: int) -> str:
        """Get message for status code."""
        messages = {
            403: "Access Forbidden - likely blocked",
            429: "Too Many Requests - rate limited",
            503: "Service Unavailable - temporary block or maintenance",
        }
        return messages.get(status, f"HTTP {status}")

    def state(self) -> dict[str, object]:
        return {
            "purpose": "Detect CAPTCHA, rate limiting, and bot challenge indicators",
            "supported_challenges": [c.value for c in ChallengeType],
            "methods": [
                "http_status_analysis",
                "response_header_analysis",
                "html_pattern_matching",
                "redirect_detection",
                "frame_injection_detection",
            ],
            "manual_review_on": ["high_severity_challenges"],
            "note": "Does not bypass challenges, only detects them for research analysis",
        }
```

**Integration into fetch pipeline**:

```python
# In asagus/layers/fetch.py or asagus/main.py
from asagus.layers.challenge_detector import ChallengeDetector

detector = ChallengeDetector(verbose=True)

async def fetch_with_challenge_detection(url: str) -> dict:
    fetch_result = await fetch_page(url)
    challenge_analysis = detector.detect(fetch_result)

    if challenge_analysis["severity"] in {"high", "block"}:
        # Store for manual review in frontend
        await job_db.mark_challenge(url, challenge_analysis)
        return {
            "status": "challenge_detected",
            "analysis": challenge_analysis,
            "requires_manual_review": True,
        }

    return {"status": "success", "fetch": fetch_result}
```

---

## Part 2: Human-Like Behavior Simulation (Tier 1)

Anti-bots analyze:
- **Mouse movement**: Linear = bot, curved = human
- **Typing speed**: Consistent = bot, variable = human
- **Scroll behavior**: Linear jumps = bot, smooth = human
- **Click patterns**: Instant = bot, delayed = human
- **Interaction timing**: Exact intervals = bot, random = human

### 2.1 WindMouse Algorithm (Physics-Based)

The WindMouse algorithm simulates realistic mouse movement using gravity, wind, and randomness:

Create `asagus/layers/human_behavior.py`:

```python
import asyncio
import random
import math
from typing import Tuple


class WindMouse:
    """
    Physics-based mouse movement simulation.
    Inspired by: https://github.com/AsfhtgkDavid/windmouse
    """

    def __init__(self, G_0: float = 9.81, drift: float = 3.5, noise_scale: float = 1.5):
        """
        G_0: gravitational constant (higher = more gravity effect)
        drift: wind effect strength (higher = more curved)
        noise_scale: randomness scale
        """
        self.G_0 = G_0
        self.drift = drift
        self.noise_scale = noise_scale

    def calculate_trajectory(
        self,
        start: Tuple[float, float],
        end: Tuple[float, float],
        duration_ms: int = 500,
    ) -> list[Tuple[float, float]]:
        """
        Calculate realistic mouse trajectory from start to end.
        Returns list of (x, y) coordinates.
        """
        distance = math.sqrt((end[0] - start[0]) ** 2 + (end[1] - start[1]) ** 2)
        
        # Trajectory duration based on distance (Fitts' law)
        if distance < 100:
            duration = max(100, min(duration_ms, 300))
        elif distance < 500:
            duration = max(150, min(duration_ms, 600))
        else:
            duration = min(duration_ms, 1000)

        # Simulation timestep
        dt = 0.01  # 10ms per step
        total_steps = int(duration / (dt * 1000))
        trajectory = [start]

        # Random wind gust
        wind_start = random.uniform(self.drift * 0.5, self.drift)
        wind_end = random.uniform(self.drift * 0.5, self.drift)

        x, y = start
        vx, vy = 0.0, 0.0

        for step in range(1, total_steps):
            progress = step / total_steps
            
            # Target velocity towards endpoint
            target_x = end[0] + random.gauss(0, 10)
            target_y = end[1] + random.gauss(0, 10)

            # Wind force (changes over time)
            wind = wind_start + (wind_end - wind_start) * progress

            # Gravity and wind forces
            ax = (target_x - x) / distance * self.G_0 + random.gauss(0, self.noise_scale)
            ay = (target_y - y) / distance * self.G_0 + random.gauss(0, self.noise_scale)

            # Apply wind
            vx += ax * dt + wind * random.gauss(0, 1) * dt
            vy += ay * dt + wind * random.gauss(0, 1) * dt

            # Damping
            vx *= 0.98
            vy *= 0.98

            # Update position
            x += vx * dt * 100  # scale factor
            y += vy * dt * 100

            trajectory.append((x, y))

        trajectory.append(end)
        return trajectory


class HumanBehavior:
    """
    Simulate human-like interaction patterns.
    Reference: https://github.com/riflosnake/HumanCursor
    """

    def __init__(self):
        self.windmouse = WindMouse()
        self.typing_variance = 0.15  # 15% variance in typing speed
        self.pause_frequency = 0.1   # 10% chance of pause between keystrokes

    async def move_mouse(
        self,
        page,
        from_pos: Tuple[float, float],
        to_pos: Tuple[float, float],
        duration_ms: int = 500,
    ) -> None:
        """Simulate realistic mouse movement via Playwright."""
        trajectory = self.windmouse.calculate_trajectory(
            from_pos, to_pos, duration_ms
        )

        # Move via many small steps (more realistic than Playwright's default)
        for i in range(1, len(trajectory)):
            x, y = trajectory[i]
            await page.mouse.move(int(x), int(y))
            await asyncio.sleep(0.01)  # Small delay between movements

    async def click(
        self,
        page,
        x: float,
        y: float,
        button: str = "left",
        delay_ms: int = 50,
        move_first: bool = True,
    ) -> None:
        """Simulate human-like click with mouse movement."""
        if move_first:
            current_pos = await page.evaluate("() => [0, 0]")  # approximate
            await self.move_mouse(page, current_pos, (x, y))

        # Random delay before click
        pre_click_delay = random.uniform(delay_ms * 0.5, delay_ms * 1.5) / 1000
        await asyncio.sleep(pre_click_delay)

        await page.mouse.click(x, y, button=button)

        # Random delay after click
        post_click_delay = random.uniform(50, 200) / 1000
        await asyncio.sleep(post_click_delay)

    async def type_text(
        self,
        page,
        selector: str,
        text: str,
        delay_ms: int = 100,
    ) -> None:
        """
        Type text with human-like timing.
        Includes random pauses, typos (then corrections).
        """
        await page.click(selector)
        await asyncio.sleep(random.uniform(100, 300) / 1000)

        for char in text:
            # Random typing speed variance
            char_delay = delay_ms * random.uniform(
                1 - self.typing_variance,
                1 + self.typing_variance
            )

            # Occasional pause (thinking)
            if random.random() < self.pause_frequency:
                await asyncio.sleep(random.uniform(200, 500) / 1000)

            await page.type(selector, char, delay=int(char_delay))

    async def scroll(
        self,
        page,
        direction: str = "down",
        steps: int = 3,
        delay_between_steps_ms: int = 200,
    ) -> None:
        """Simulate human-like scrolling (not instant)."""
        for _ in range(steps):
            await page.evaluate(
                f"() => window.scrollBy(0, {300 if direction == 'down' else -300})"
            )
            await asyncio.sleep(
                random.uniform(delay_between_steps_ms * 0.5, delay_between_steps_ms * 1.5) / 1000
            )

    async def random_idle(self, min_ms: int = 100, max_ms: int = 500) -> None:
        """Random idle period (thinking/looking at content)."""
        delay = random.uniform(min_ms, max_ms) / 1000
        await asyncio.sleep(delay)

    def state(self) -> dict[str, object]:
        return {
            "algorithms": ["windmouse_physics", "human_typing_variance", "scroll_smoothing"],
            "features": [
                "realistic_mouse_trajectories",
                "variable_typing_speed",
                "random_interaction_delays",
                "smooth_scrolling",
                "random_idle_periods",
            ],
            "purpose": "Evade behavioral biometrics detection in bot challenges",
        }
```

**Usage in browser automation**:

```python
# In asagus/layers/browser.py
from asagus.layers.human_behavior import HumanBehavior

async def render_with_human_behavior(url: str, actions: list[dict]) -> str:
    """Render page with human-like interaction."""
    human = HumanBehavior()

    async with self._page() as page:
        await page.goto(url)

        for action in actions:
            if action["type"] == "click":
                await human.click(
                    page,
                    action["x"],
                    action["y"],
                )
            elif action["type"] == "type":
                await human.type_text(
                    page,
                    action["selector"],
                    action["text"],
                )
            elif action["type"] == "scroll":
                await human.scroll(page, direction=action.get("direction", "down"))
            elif action["type"] == "idle":
                await human.random_idle()

            await human.random_idle(200, 500)  # Pause between actions

        return await page.content()
```

---

## Part 3: Advanced Browser Fingerprinting (Tier 1)

Modern fingerprinting goes beyond User-Agent. Detection systems analyze:

- **Canvas fingerprinting**: WebGL texture rendering hash
- **AudioContext**: Audio context state hash
- **Font detection**: Installed fonts comparison
- **Hardware**: CPU cores, RAM hints, screen resolution
- **WebRTC**: IP leak detection
- **Timezone, locale, plugins**

Create `asagus/layers/fingerprint_advanced.py`:

```python
import hashlib
from typing import Optional


class AdvancedFingerprinting:
    """
    Advanced browser fingerprinting for evasion research.
    References:
    - FingerprintJS: https://github.com/fingerprintjs/fingerprintjs
    - CreepJS: https://github.com/abrahamjuliot/creepjs
    """

    async def collect_fingerprint_signals(self, page) -> dict[str, object]:
        """
        Collect comprehensive fingerprint signals from browser context.
        Used for research into detection mechanisms.
        """

        # 1. Canvas fingerprinting
        canvas_fp = await self._canvas_fingerprint(page)

        # 2. WebGL fingerprinting
        webgl_fp = await self._webgl_fingerprint(page)

        # 3. Audio context fingerprinting
        audio_fp = await self._audio_fingerprint(page)

        # 4. Font detection
        fonts = await self._detect_fonts(page)

        # 5. Hardware/system info
        hardware = await self._detect_hardware(page)

        # 6. WebRTC detection
        webrtc = await self._detect_webrtc(page)

        # 7. Plugin enumeration
        plugins = await self._detect_plugins(page)

        # 8. TLS/cipher analysis
        tls_info = await self._collect_tls_info(page)

        combined_fingerprint = {
            "canvas": canvas_fp,
            "webgl": webgl_fp,
            "audio": audio_fp,
            "fonts": fonts,
            "hardware": hardware,
            "webrtc": webrtc,
            "plugins": plugins,
            "tls": tls_info,
            "entropy_score": self._calculate_entropy(
                canvas_fp, webgl_fp, audio_fp, fonts, hardware
            ),
        }

        return combined_fingerprint

    async def _canvas_fingerprint(self, page) -> dict[str, str]:
        """Canvas fingerprinting via rendering."""
        canvas_script = """
        () => {
            try {
                const canvas = document.createElement('canvas');
                canvas.width = 280;
                canvas.height = 60;
                const ctx = canvas.getContext('2d');
                ctx.textBaseline = 'top';
                ctx.font = '14px Arial';
                ctx.textBaseline = 'alphabetic';
                ctx.fillStyle = '#f60';
                ctx.fillRect(125, 1, 62, 20);
                ctx.fillStyle = '#069';
                ctx.fillText('Browser Fingerprint', 2, 15);
                ctx.fillStyle = 'rgba(102, 204, 0, 0.7)';
                ctx.fillText('Browser Fingerprint', 4, 17);
                const dataUrl = canvas.toDataURL();
                return {
                    hash: dataUrl.substring(0, 100),
                    supports: 'canvas' in document.createElement('canvas'),
                };
            } catch(e) {
                return { error: e.message };
            }
        }
        """
        return await page.evaluate(canvas_script)

    async def _webgl_fingerprint(self, page) -> dict[str, object]:
        """WebGL fingerprinting."""
        webgl_script = """
        () => {
            try {
                const canvas = document.createElement('canvas');
                const gl = canvas.getContext('webgl') || 
                           canvas.getContext('experimental-webgl');
                if (!gl) return { error: 'WebGL not supported' };
                
                const debugInfo = gl.getExtension('WEBGL_debug_renderer_info');
                return {
                    vendor: gl.getParameter(debugInfo.UNMASKED_VENDOR_WEBGL),
                    renderer: gl.getParameter(debugInfo.UNMASKED_RENDERER_WEBGL),
                    supported_extensions: gl.getSupportedExtensions().length,
                };
            } catch(e) {
                return { error: e.message };
            }
        }
        """
        return await page.evaluate(webgl_script)

    async def _audio_fingerprint(self, page) -> dict[str, object]:
        """AudioContext fingerprinting."""
        audio_script = """
        () => {
            try {
                const AudioContext = window.AudioContext || 
                                    window.webkitAudioContext;
                if (!AudioContext) return { error: 'AudioContext not supported' };
                
                const context = new AudioContext();
                const oscillator = context.createOscillator();
                const analyser = context.createAnalyser();
                const gain = context.createGain();
                const scriptProcessor = context.createScriptProcessor(4096, 1, 1);
                
                gain.gain.value = 0; // mute
                oscillator.connect(analyser);
                analyser.connect(scriptProcessor);
                scriptProcessor.connect(gain);
                gain.connect(context.destination);
                
                return {
                    sample_rate: context.sampleRate,
                    state: context.state,
                    max_channel_count: context.destination.maxChannelCount,
                    supported: true,
                };
            } catch(e) {
                return { error: e.message };
            }
        }
        """
        return await page.evaluate(audio_script)

    async def _detect_fonts(self, page) -> list[str]:
        """Detect available fonts."""
        fonts_script = """
        () => {
            const baseFonts = ['monospace', 'sans-serif', 'serif'];
            const testFonts = [
                'Akbar', 'Andalus', 'Angsana New', 'AngsanaUPC',
                'Browallia New', 'BrowalliaUPC', 'CordiaNew', 'Cordia UPC',
                'DilleniaUPC', 'Dotum', 'DotumChe', 'Euphemia UCAS',
                'MV Boli', 'Miriam Fixed', 'Microsoft Sans Serif',
                'Segoe UI', 'Tahoma', 'Times New Roman', 'Verdana',
            ];
            
            const measurer = document.createElement('span');
            measurer.style.visibility = 'hidden';
            document.body.appendChild(measurer);
            
            const detected = [];
            for (const font of testFonts) {
                measurer.style.fontFamily = `"${font}", sans-serif`;
                const width1 = measurer.offsetWidth;
                
                measurer.style.fontFamily = `"${font}", monospace`;
                const width2 = measurer.offsetWidth;
                
                if (width1 !== width2) {
                    detected.push(font);
                }
            }
            
            document.body.removeChild(measurer);
            return detected;
        }
        """
        return await page.evaluate(fonts_script)

    async def _detect_hardware(self, page) -> dict[str, object]:
        """Detect hardware capabilities."""
        hardware_script = """
        () => {
            return {
                cpu_cores: navigator.hardwareConcurrency,
                device_memory: navigator.deviceMemory,
                max_touch_points: navigator.maxTouchPoints,
                platform: navigator.platform,
                language: navigator.language,
                timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
                screen_width: window.screen.width,
                screen_height: window.screen.height,
                color_depth: window.screen.colorDepth,
                pixel_depth: window.screen.pixelDepth,
            };
        }
        """
        return await page.evaluate(hardware_script)

    async def _detect_webrtc(self, page) -> dict[str, object]:
        """Detect WebRTC and potential IP leak."""
        webrtc_script = """
        () => {
            return {
                webrtc_available: !!(window.RTCPeerConnection || 
                                      window.webkitRTCPeerConnection ||
                                      window.mozRTCPeerConnection),
                media_devices_available: !!navigator.mediaDevices,
            };
        }
        """
        return await page.evaluate(webrtc_script)

    async def _detect_plugins(self, page) -> dict[str, object]:
        """Detect browser plugins."""
        plugins_script = """
        () => {
            const plugins = [];
            for (let plugin of navigator.plugins) {
                plugins.push({
                    name: plugin.name,
                    description: plugin.description,
                });
            }
            return { plugin_count: plugins.length, plugins };
        }
        """
        return await page.evaluate(plugins_script)

    async def _collect_tls_info(self, page) -> dict[str, object]:
        """
        Collect TLS/SSL information.
        Note: Limited from JS; better info via HTTP/2 fingerprinting
        from python-tls-client or curl-impersonate.
        """
        return {
            "note": "TLS fingerprinting requires HTTP client level access",
            "recommendation": "Use python-tls-client or curl-impersonate for deeper analysis",
        }

    def _calculate_entropy(self, *fingerprints) -> float:
        """
        Rough entropy calculation for fingerprint uniqueness.
        Higher = more unique = more likely to be detected.
        """
        combined = str(fingerprints)
        entropy_score = len(set(combined)) / len(combined) if combined else 0
        return round(entropy_score, 2)

    def state(self) -> dict[str, object]:
        return {
            "purpose": "Collect advanced fingerprinting signals for research analysis",
            "signals_collected": [
                "canvas_hash",
                "webgl_vendor_renderer",
                "audio_context_properties",
                "installed_fonts",
                "hardware_capabilities",
                "webrtc_availability",
                "browser_plugins",
                "timezone_locale",
                "screen_resolution",
            ],
            "entropy_analysis": True,
            "use_case": "Benchmark anti-bot detection mechanisms",
        }
```

---

## Part 4: GPU/TPU Detection & Acceleration (Tier 2)

For CAPTCHA solving and heavy computation, use GPU if available:

Create `asagus/layers/compute_accelerator.py`:

```python
import os
from typing import Literal


class ComputeAccelerator:
    """
    Detect and use GPU/TPU/DPU for acceleration.
    Reference: PyTorch, TensorFlow detection patterns.
    """

    def __init__(self, allow_gpu: bool = True, allow_tpu: bool = False):
        self.allow_gpu = allow_gpu
        self.allow_tpu = allow_tpu
        self.device = self._detect_device()

    def _detect_device(self) -> str:
        """Detect available accelerator."""
        if not self.allow_gpu:
            return "cpu"

        # 1. Check for NVIDIA GPU
        if self._has_nvidia_gpu():
            return "nvidia_gpu"

        # 2. Check for AMD GPU
        if self._has_amd_gpu():
            return "amd_gpu"

        # 3. Check for Apple Silicon
        if self._has_apple_gpu():
            return "apple_gpu"

        # 4. Check for Intel GPU/Xe
        if self._has_intel_gpu():
            return "intel_gpu"

        # 5. Check for TPU (Google Cloud)
        if self.allow_tpu and self._has_tpu():
            return "tpu"

        return "cpu"

    def _has_nvidia_gpu(self) -> bool:
        """Check for NVIDIA GPU."""
        try:
            import torch
            return torch.cuda.is_available()
        except ImportError:
            return False

    def _has_amd_gpu(self) -> bool:
        """Check for AMD GPU (ROCm)."""
        try:
            import torch
            return torch.version.hip is not None
        except ImportError:
            return False

    def _has_apple_gpu(self) -> bool:
        """Check for Apple Silicon (Metal)."""
        try:
            import platform
            if platform.system() == "Darwin":
                import torch
                return torch.backends.mps.is_available()
        except ImportError:
            return False
        return False

    def _has_intel_gpu(self) -> bool:
        """Check for Intel GPU (oneAPI/OpenVINO)."""
        try:
            # Check for OpenVINO
            from openvino.runtime import Core
            core = Core()
            devices = core.available_devices
            return any("GPU" in d for d in devices)
        except ImportError:
            return False

    def _has_tpu(self) -> bool:
        """Check for Google Cloud TPU."""
        return "TPU_NAME" in os.environ or "COLAB_TPU_ADDR" in os.environ

    async def solve_captcha_with_gpu(
        self,
        image_path: str,
        model_name: str = "paddleocr",
    ) -> str:
        """
        Use GPU to solve OCR-based CAPTCHA.
        Note: For research/educational purposes only.
        """
        device = self.device

        if model_name == "paddleocr":
            return await self._solve_with_paddleocr(image_path, device)
        elif model_name == "paddleocr":
            return await self._solve_with_easyocr(image_path, device)

        return ""

    async def _solve_with_paddleocr(self, image_path: str, device: str) -> str:
        """Use PaddleOCR with GPU acceleration."""
        try:
            from paddleocr import PaddleOCR
            # use_gpu parameter: False for CPU, True for GPU
            use_gpu = device != "cpu"
            ocr = PaddleOCR(use_gpu=use_gpu, lang="en")
            result = ocr.ocr(image_path)
            return " ".join([line[0][1] for line in result[0]]) if result else ""
        except ImportError:
            return ""

    async def _solve_with_easyocr(self, image_path: str, device: str) -> str:
        """Use EasyOCR with GPU acceleration."""
        try:
            import easyocr
            reader = easyocr.Reader(
                ["en"],
                gpu=(device != "cpu"),
            )
            results = reader.readtext(image_path)
            return " ".join([text[1] for text in results])
        except ImportError:
            return ""

    async def process_embeddings_with_gpu(
        self,
        texts: list[str],
    ) -> list:
        """Use GPU for embedding generation."""
        device = self.device

        if device == "cpu":
            return await self._embeddings_cpu(texts)

        try:
            from sentence_transformers import SentenceTransformer
            device_map = "cuda" if "gpu" in device else "cpu"
            model = SentenceTransformer(
                "all-MiniLM-L6-v2",
                device=device_map,
            )
            return model.encode(texts)
        except ImportError:
            return await self._embeddings_cpu(texts)

    async def _embeddings_cpu(self, texts: list[str]) -> list:
        """Fallback to CPU embeddings."""
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("all-MiniLM-L6-v2")
        return model.encode(texts)

    def get_config(self) -> dict[str, object]:
        """Get acceleration configuration."""
        return {
            "detected_device": self.device,
            "gpu_enabled": self.allow_gpu,
            "tpu_enabled": self.allow_tpu,
            "capabilities": {
                "ocr_acceleration": "gpu" in self.device,
                "embedding_acceleration": "gpu" in self.device or "tpu" in self.device,
                "ml_inference": "gpu" in self.device or "tpu" in self.device,
            },
        }

    def state(self) -> dict[str, object]:
        return {
            "device": self.device,
            "capabilities": self.get_config()["capabilities"],
            "uses": [
                "CAPTCHA_OCR_solving",
                "Embedding_generation",
                "ML_model_inference",
                "Computer_vision_tasks",
            ],
        }
```

---

## Part 5: Deep Agent Mode - Browser Action DSL (Tier 1)

Allow complex browser interaction workflows:

Create `asagus/layers/browser_actions.py`:

```python
from enum import Enum
from typing import Optional, Any
from pydantic import BaseModel
from asagus.models import utc_now


class BrowserActionType(str, Enum):
    navigate = "navigate"
    click = "click"
    fill = "fill"
    select = "select"
    type = "type"
    wait_for_selector = "wait_for_selector"
    wait_for_navigation = "wait_for_navigation"
    screenshot = "screenshot"
    extract_text = "extract_text"
    extract_table = "extract_table"
    extract_json = "extract_json"
    evaluate_js = "evaluate_js"
    set_viewport = "set_viewport"
    scroll = "scroll"
    keyboard = "keyboard"
    mouse_move = "mouse_move"
    human_pause = "human_pause"


class BrowserAction(BaseModel):
    """Typed browser action."""
    action: BrowserActionType
    url: Optional[str] = None  # navigate
    selector: Optional[str] = None  # click, fill, etc.
    value: Optional[str] = None  # fill, type, select
    timeout_ms: int = 30000
    xpath: Optional[str] = None  # alternative to CSS selector
    code: Optional[str] = None  # evaluate_js
    width: Optional[int] = None  # set_viewport
    height: Optional[int] = None
    direction: Optional[str] = None  # scroll
    key: Optional[str] = None  # keyboard
    x: Optional[float] = None  # mouse_move
    y: Optional[float] = None
    duration_ms: Optional[int] = None  # human_pause
    human_like: bool = True  # use HumanBehavior
    metadata: dict = {}


class BrowserActionResult(BaseModel):
    """Result of browser action execution."""
    action: BrowserActionType
    success: bool
    timestamp: str
    result: Any = None
    error: Optional[str] = None
    duration_ms: float
    metadata: dict = {}


class BrowserActionExecutor:
    """
    Execute browser actions with human-like behavior.
    Used in Deep Agent Mode.
    """

    def __init__(self, page, human_behavior=None):
        self.page = page
        self.human_behavior = human_behavior
        self.trace: list[BrowserActionResult] = []
        self.action_budget = 20  # max actions per session

    async def execute_action(self, action: BrowserAction) -> BrowserActionResult:
        """Execute a single browser action."""
        import time
        from asagus.layers.human_behavior import HumanBehavior

        if not self.human_behavior and action.human_like:
            self.human_behavior = HumanBehavior()

        start_time = time.time()
        success = False
        result = None
        error = None

        try:
            if action.action == BrowserActionType.navigate:
                await self.page.goto(action.url, timeout=action.timeout_ms)
                success = True

            elif action.action == BrowserActionType.click:
                if action.human_like and self.human_behavior:
                    # Get element position
                    box = await self.page.query_selector(action.selector)
                    if box:
                        bbox = await box.bounding_box()
                        await self.human_behavior.click(
                            self.page,
                            bbox["x"] + bbox["width"] / 2,
                            bbox["y"] + bbox["height"] / 2,
                        )
                else:
                    await self.page.click(action.selector)
                success = True

            elif action.action == BrowserActionType.fill:
                await self.page.fill(action.selector, action.value)
                success = True

            elif action.action == BrowserActionType.type:
                if action.human_like and self.human_behavior:
                    await self.human_behavior.type_text(
                        self.page,
                        action.selector,
                        action.value,
                    )
                else:
                    await self.page.type(action.selector, action.value)
                success = True

            elif action.action == BrowserActionType.select:
                await self.page.select_option(action.selector, action.value)
                success = True

            elif action.action == BrowserActionType.wait_for_selector:
                await self.page.wait_for_selector(
                    action.selector,
                    timeout=action.timeout_ms
                )
                success = True

            elif action.action == BrowserActionType.screenshot:
                result = await self.page.screenshot(path=action.value)
                success = True

            elif action.action == BrowserActionType.extract_text:
                elements = await self.page.query_selector_all(action.selector)
                result = [await e.text_content() for e in elements]
                success = True

            elif action.action == BrowserActionType.extract_table:
                result = await self.page.evaluate(f"""
                    () => {{
                        const table = document.querySelector('{action.selector}');
                        const rows = [];
                        table.querySelectorAll('tr').forEach(tr => {{
                            const cells = [];
                            tr.querySelectorAll('td,th').forEach(td => cells.push(td.textContent));
                            rows.push(cells);
                        }});
                        return rows;
                    }}
                """)
                success = True

            elif action.action == BrowserActionType.evaluate_js:
                result = await self.page.evaluate(action.code)
                success = True

            elif action.action == BrowserActionType.scroll:
                direction = action.direction or "down"
                if action.human_like and self.human_behavior:
                    await self.human_behavior.scroll(self.page, direction)
                else:
                    amount = 300 if direction == "down" else -300
                    await self.page.evaluate(f"() => window.scrollBy(0, {amount})")
                success = True

            elif action.action == BrowserActionType.human_pause:
                duration_ms = action.duration_ms or 500
                if self.human_behavior:
                    await self.human_behavior.random_idle(duration_ms * 0.5, duration_ms)
                success = True

            elif action.action == BrowserActionType.set_viewport:
                await self.page.set_viewport_size({
                    "width": action.width or 1365,
                    "height": action.height or 900
                })
                success = True

        except Exception as e:
            success = False
            error = str(e)

        duration_ms = (time.time() - start_time) * 1000

        action_result = BrowserActionResult(
            action=action.action,
            success=success,
            timestamp=utc_now().isoformat(),
            result=result,
            error=error,
            duration_ms=duration_ms,
            metadata=action.metadata,
        )

        self.trace.append(action_result)

        if len(self.trace) >= self.action_budget:
            raise RuntimeError(f"Action budget exceeded: {self.action_budget}")

        return action_result

    async def execute_workflow(self, actions: list[BrowserAction]) -> list[BrowserActionResult]:
        """Execute workflow of actions."""
        results = []
        for action in actions:
            result = await self.execute_action(action)
            results.append(result)
            if not result.success:
                break  # Stop on first failure
        return results

    def get_trace(self) -> list[dict]:
        """Get execution trace for debugging/replay."""
        return [r.model_dump() for r in self.trace]
```

**Example workflow**:

```python
# Search for a restaurant, fill form, submit
workflow = [
    BrowserAction(
        action=BrowserActionType.navigate,
        url="https://example-restaurant-directory.com",
    ),
    BrowserAction(
        action=BrowserActionType.wait_for_selector,
        selector="input[name='query']",
        timeout_ms=10000,
    ),
    BrowserAction(
        action=BrowserActionType.fill,
        selector="input[name='query']",
        value="Italian Restaurant",
        human_like=True,
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

executor = BrowserActionExecutor(page, human_behavior)
results = await executor.execute_workflow(workflow)
```

---

## Part 6: TLS/HTTP Fingerprinting Evasion (Tier 2)

Anti-bots analyze TLS/HTTP2 fingerprints. Use specialized libraries:

### Dependencies to Add

```bash
# Recommended additions to requirements.txt

# CAPTCHA & solving
pip install capsolver-py>=1.0.0

# Human behavior & OCR
pip install paddleocr>=2.7.0
pip install easyocr>=1.7.0

# Advanced fingerprinting
pip install selenium-stealth>=1.0.1

# TLS fingerprinting tools (optional, advanced)
pip install python-tls-client>=0.2.0
# or: pip install curl-impersonate  (if building locally)

# GPU acceleration
pip install torch>=2.0.0  # with CUDA support: torch[cu118]
pip install tensorflow>=2.13.0  # with CUDA support

# Vision models for CAPTCHA solving
pip install transformers>=4.30.0
pip install timm>=0.9.0  # for vision models
```

---

## Part 7: Resource Governance & Scheduling (Tier 3)

Create `asagus/layers/resource_governor.py`:

```python
import asyncio
import os
from typing import Optional


class ResourceGovernor:
    """
    Manage CPU, browser, and LLM concurrency with backpressure.
    """

    def __init__(
        self,
        cpu_workers: int = None,
        browser_pool_size: int = 3,
        llm_concurrency: int = 5,
        queue_max_size: int = 1000,
    ):
        self.cpu_workers = cpu_workers or max(1, os.cpu_count() - 1)
        self.browser_pool_size = browser_pool_size
        self.llm_concurrency = llm_concurrency
        self.queue_max_size = queue_max_size

        # Semaphores for concurrency control
        self.cpu_semaphore = asyncio.Semaphore(self.cpu_workers)
        self.browser_semaphore = asyncio.Semaphore(self.browser_pool_size)
        self.llm_semaphore = asyncio.Semaphore(self.llm_concurrency)

        # Queues
        self.cpu_queue_size = 0
        self.browser_queue_size = 0
        self.llm_queue_size = 0

    async def cpu_task(self, coro):
        """Run CPU-bound task with concurrency control."""
        async with self.cpu_semaphore:
            self.cpu_queue_size += 1
            try:
                return await coro
            finally:
                self.cpu_queue_size -= 1

    async def browser_task(self, coro):
        """Run browser task with concurrency control."""
        async with self.browser_semaphore:
            self.browser_queue_size += 1
            try:
                return await coro
            finally:
                self.browser_queue_size -= 1

    async def llm_task(self, coro):
        """Run LLM task with concurrency control."""
        async with self.llm_semaphore:
            self.llm_queue_size += 1
            try:
                return await coro
            finally:
                self.llm_queue_size -= 1

    def can_accept_work(self) -> bool:
        """Check if queue has capacity."""
        total_queue = (
            self.cpu_queue_size +
            self.browser_queue_size +
            self.llm_queue_size
        )
        return total_queue < self.queue_max_size

    def get_metrics(self) -> dict:
        """Get resource utilization metrics."""
        return {
            "cpu_workers": self.cpu_workers,
            "cpu_queue_size": self.cpu_queue_size,
            "cpu_utilization": self.cpu_queue_size / self.cpu_workers,
            "browser_pool_size": self.browser_pool_size,
            "browser_queue_size": self.browser_queue_size,
            "browser_utilization": self.browser_queue_size / self.browser_pool_size,
            "llm_concurrency": self.llm_concurrency,
            "llm_queue_size": self.llm_queue_size,
            "llm_utilization": self.llm_queue_size / self.llm_concurrency,
            "can_accept_work": self.can_accept_work(),
        }
```

---

## Part 8: Extraction Recipes (Tier 3)

Create reusable extraction templates:

```python
# asagus/layers/extraction_recipes.py

class ExtractionRecipe:
    """Base extraction recipe."""
    
    def __init__(self):
        self.name = "generic"
        self.domain_patterns = [".*"]
    
    async def extract(self, fetch_result, dom_tools, llm_client):
        raise NotImplementedError


class RestaurantRecipe(ExtractionRecipe):
    """Restaurant-specific extraction."""
    
    def __init__(self):
        super().__init__()
        self.name = "restaurant"
        self.domain_patterns = [
            "yelp.com", "zomato.com", "tripadvisor.com",
            "doordash.com", "ubereats.com", "justeat.com",
        ]
        self.selectors = {
            "name": "h1, h2.restaurant-name",
            "rating": ".rating, .stars, [data-testid='rating']",
            "address": "[data-testid='address'], .address, .location",
            "phone": ".phone-number, [href^='tel:']",
            "website": "a[href*='www'], [data-testid='url']",
            "cuisine": ".cuisine-type, .tags",
            "hours": ".hours, .operating-hours, [aria-label*='Hours']",
        }
    
    async def extract(self, fetch_result, dom_tools, llm_client):
        """Extract restaurant data."""
        html = fetch_result.body
        data = {}
        
        for field, selector in self.selectors.items():
            values = dom_tools.text_by_css(html, selector)
            data[field] = values[0] if values else None
        
        return data


class DirectoryProfileRecipe(ExtractionRecipe):
    """Business directory profile extraction."""
    
    def __init__(self):
        super().__init__()
        self.name = "directory_profile"
        self.domain_patterns = [
            "google.com/maps", "linkedin.com", "crunchbase.com",
            "yellowpages.com", "superpages.com",
        ]
    
    async def extract(self, fetch_result, dom_tools, llm_client):
        """Extract directory profile."""
        html = fetch_result.body
        
        # Extract JSON-LD if present
        import re
        import json
        
        ld_json_matches = re.findall(
            r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
            html,
            flags=re.I | re.S
        )
        
        if ld_json_matches:
            try:
                return json.loads(ld_json_matches[0])
            except json.JSONDecodeError:
                pass
        
        # Fallback to structured extraction
        return {
            "name": dom_tools.text_by_css(html, "h1, .title")[0] if dom_tools.text_by_css(html, "h1, .title") else None,
            "description": dom_tools.text_by_css(html, ".description, p")[0] if dom_tools.text_by_css(html, ".description, p") else None,
            "contact": dom_tools.text_by_css(html, ".contact, [data-contact]"),
        }


class RecipeRegistry:
    """Manage available extraction recipes."""
    
    def __init__(self):
        self.recipes = {
            "generic": ExtractionRecipe(),
            "restaurant": RestaurantRecipe(),
            "directory": DirectoryProfileRecipe(),
        }
    
    def get_recipe(self, name: str):
        return self.recipes.get(name, self.recipes["generic"])
```

---

## Summary: Implementation Priority

### **Must Implement Now** (Highest ROI for research):

1. ✅ **ChallengeDetector** - Identify CAPTCHA/bot blocks
2. ✅ **HumanBehavior + WindMouse** - Evade behavior analysis
3. ✅ **AdvancedFingerprinting** - Understand detection signals
4. ✅ **BrowserActions DSL** - Deep Agent Mode workflows

### **Should Implement Soon** (High Value):

5. ✅ **ComputeAccelerator** - GPU CAPTCHA solving
6. ✅ **ResourceGovernor** - Better concurrency
7. ✅ **ExtractionRecipes** - Domain-specific extraction

### **Optional** (Advanced/Specialized):

8. TLS Evasion (python-tls-client)
9. Anti-fingerprinting patches (Selenium Stealth)
10. Custom browser profiles

---

## References & Further Reading

**CAPTCHA & Bot Detection:**
- reCAPTCHA v3 docs
- Cloudflare Turnstile documentation
- PerimeterX API docs

**Fingerprinting:**
- FingerprintJS: https://github.com/fingerprintjs/fingerprintjs
- CreepJS: https://github.com/abrahamjuliot/creepjs
- BrowserLeaks: https://browserleaks.com

**Evasion & Behavior:**
- Camoufox: https://github.com/daijro/camoufox
- HumanCursor: https://github.com/riflosnake/HumanCursor
- WindMouse: https://github.com/AsfhtgkDavid/windmouse

**Testing:**
- Pixelscan: https://pixelscan.net
- Browserstack automation
- Puppeteer/Playwright testing

---

## Safety & Legal Notes

✅ **Allowed (Research & Security Testing):**
- Detecting challenges (no bypass)
- Fingerprint collection (for understanding detection)
- Human-like behavior simulation (research)
- CAPTCHA solving analysis
- Rate-limit handling
- Anti-bot mechanism research

❌ **NOT Allowed:**
- Credential theft/harvesting
- Social media account automation (mass-follow, spam)
- Bypassing platform terms of service
- Illegal unauthorized access
- Identity fraud

This implementation is for **security research, CAPTCHA development, and anti-bot testing** — legitimate use cases under academic/commercial security testing frameworks.

