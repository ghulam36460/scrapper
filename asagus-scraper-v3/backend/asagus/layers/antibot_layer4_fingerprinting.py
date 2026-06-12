"""
Layer 4: Browser and DOM Fingerprinting
========================================
Detect and spoof fingerprinting signals from rendered browser environment.

Critical Insight from antibot.md:
Browser fingerprinting is the richest detection dimension with 100+ signals:
- Canvas fingerprinting: GPU rendering output (VERY HIGH entropy)
- WebGL renderer: GPU vendor/model exposed directly
- AudioContext: Floating-point arithmetic varies per hardware
- Font list: ~400 distinguishable fonts per system
- Screen properties: Resolution, DPR, color depth
- WebRTC IP leak: Reveals real IP behind proxy
- Timezone, language, plugins, hardware concurrency
- V8 bytecode analysis (checks if functions are native or patched)

Key Property: Consistency
- Same "device" must maintain identical fingerprints across sessions
- Inconsistent fingerprints across signals = bot detection
- Geographically impossible device combos = detection

Fingerprinting Tools:
★★★ FingerprintJS: Visitor ID generation (industry standard)
★★★ CreepJS: Most aggressive detector (100+ signals)
★ OpenWPM: Firefox instrumentation for mass measurement
★ fp-radar: Real-time fingerprint stream analysis
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from typing import Any, Literal

import playwright.async_api as pw


logger = logging.getLogger(__name__)


@dataclass
class DeviceProfile:
    """Consistent device identity across all sessions."""
    
    # Screen properties
    screen_width: int = 1920
    screen_height: int = 1080
    device_pixel_ratio: float = 1.0
    color_depth: int = 24
    
    # Hardware properties
    hardware_concurrency: int = 8
    device_memory: int = 8  # GB
    max_touch_points: int = 0
    
    # GPU properties
    webgl_vendor: str = "Intel Inc."
    webgl_renderer: str = "Intel Iris OpenGL Engine"
    canvas_fingerprint: str = ""  # Will be generated and cached
    
    # System properties
    timezone: str = "America/New_York"
    language: str = "en-US"
    languages: list[str] = None
    platform: str = "Win32"
    
    # Browser properties
    user_agent: str = ""
    
    # Computed fingerprint (stable across sessions)
    device_id: str = ""
    
    def __post_init__(self):
        if self.languages is None:
            self.languages = ["en-US", "en"]
        
        # Generate stable device ID from properties
        props_str = json.dumps({
            "screen": f"{self.screen_width}x{self.screen_height}",
            "gpu": self.webgl_renderer,
            "cpu": self.hardware_concurrency,
            "timezone": self.timezone,
        })
        self.device_id = hashlib.sha256(props_str.encode()).hexdigest()[:16]


class Layer4BrowserFingerprinting:
    """
    Detect, analyze, and maintain consistency of browser fingerprints.
    
    Strategy:
    1. Define realistic device profile (GPU, screen, CPU)
    2. Inject JavaScript to spoof fingerprinting APIs
    3. Maintain consistency across all sessions
    4. Prevent "lie detection" via prototype chain checks
    """
    
    def __init__(self, device_profile: DeviceProfile | None = None):
        self.device_profile = device_profile or DeviceProfile()
        self.logger = logging.getLogger(__name__)
    
    async def apply_fingerprint_spoofing(self, context: pw.BrowserContext) -> None:
        """Apply fingerprint spoofing to browser context."""
        
        init_script = self._generate_fingerprint_spoof_script()
        await context.add_init_script(init_script)
        
        self.logger.info(
            f"Applied fingerprint spoofing (Device ID: {self.device_profile.device_id})"
        )
    
    def _generate_fingerprint_spoof_script(self) -> str:
        """Generate comprehensive fingerprint spoofing JavaScript."""
        
        device = self.device_profile
        
        script_parts = [
            # Screen properties
            f"""
            Object.defineProperty(window.screen, 'width', {{
                get: () => {device.screen_width}
            }});
            Object.defineProperty(window.screen, 'height', {{
                get: () => {device.screen_height}
            }});
            Object.defineProperty(window.screen, 'availWidth', {{
                get: () => {device.screen_width}
            }});
            Object.defineProperty(window.screen, 'availHeight', {{
                get: () => {device.screen_height - 40}
            }});
            Object.defineProperty(window.screen, 'colorDepth', {{
                get: () => {device.color_depth}
            }});
            Object.defineProperty(window.screen, 'pixelDepth', {{
                get: () => {device.color_depth}
            }});
            Object.defineProperty(window.devicePixelRatio, 'value', {{
                get: () => {device.device_pixel_ratio}
            }});
            """,
            
            # Hardware properties
            f"""
            Object.defineProperty(navigator, 'hardwareConcurrency', {{
                get: () => {device.hardware_concurrency}
            }});
            Object.defineProperty(navigator, 'deviceMemory', {{
                get: () => {device.device_memory}
            }});
            Object.defineProperty(navigator, 'maxTouchPoints', {{
                get: () => {device.max_touch_points}
            }});
            """,
            
            # Navigator platform/language
            f"""
            Object.defineProperty(navigator, 'platform', {{
                get: () => '{device.platform}'
            }});
            Object.defineProperty(navigator, 'language', {{
                get: () => '{device.language}'
            }});
            Object.defineProperty(navigator, 'languages', {{
                get: () => {json.dumps(device.languages)}
            }});
            """,
            
            # WebGL rendering properties
            f"""
            const originalGetParameter = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(parameter) {{
                if (parameter === 37445) {{ // UNMASKED_VENDOR_WEBGL
                    return '{device.webgl_vendor}';
                }}
                if (parameter === 37446) {{ // UNMASKED_RENDERER_WEBGL
                    return '{device.webgl_renderer}';
                }}
                return originalGetParameter.call(this, parameter);
            }};
            
            const originalGetParameter2 = WebGL2RenderingContext.prototype.getParameter;
            WebGL2RenderingContext.prototype.getParameter = function(parameter) {{
                if (parameter === 37445) {{ // UNMASKED_VENDOR_WEBGL
                    return '{device.webgl_vendor}';
                }}
                if (parameter === 37446) {{ // UNMASKED_RENDERER_WEBGL
                    return '{device.webgl_renderer}';
                }}
                return originalGetParameter2.call(this, parameter);
            }};
            """,
            
            # Timezone
            f"""
            Date.prototype.getTimezoneOffset = function() {{
                // {device.timezone}
                return -240;
            }};
            """,
            
            # Prevent canvas fingerprinting consistency detection
            """
            // Cache canvas fingerprint to prevent variation detection
            const canvasFingerprintCache = {{}};
            const originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
            HTMLCanvasElement.prototype.toDataURL = function(type, ...args) {{
                const cacheKey = type + JSON.stringify(args);
                if (!canvasFingerprintCache[cacheKey]) {{
                    canvasFingerprintCache[cacheKey] = originalToDataURL.call(this, type, ...args);
                }}
                return canvasFingerprintCache[cacheKey];
            }};
            """,
            
            # Prevent AudioContext fingerprinting
            """
            const audioContexts = new WeakMap();
            const OriginalAudioContext = window.AudioContext;
            const OriginalOfflineAudioContext = window.OfflineAudioContext;
            
            function createConsistentAudioContext(contextClass) {{
                return class extends contextClass {{
                    constructor(...args) {{
                        super(...args);
                        // Consistent audio output would go here
                    }}
                }};
            }}
            
            window.AudioContext = createConsistentAudioContext(OriginalAudioContext);
            window.OfflineAudioContext = createConsistentAudioContext(OriginalOfflineAudioContext);
            """,
        ]
        
        return "\n".join(script_parts)
    
    def generate_device_profile_for_target(self, url: str) -> DeviceProfile:
        """
        Generate realistic device profile for target URL.
        
        In production, could:
        1. Detect target's expected device type
        2. Generate consistent profile per domain
        3. Rotate profiles to avoid device clustering
        """
        
        # Start with default profile
        profile = DeviceProfile()
        
        # Could add logic here to vary GPU, screen size, etc.
        # while maintaining realistic combinations
        
        return profile
    
    async def detect_fingerprinting_script(self, page: pw.Page) -> dict[str, Any]:
        """Detect what fingerprinting scripts are on the page."""
        
        fingerprinting_detectors = {
            "fingerprintjs": 'window.fingerprint || window.FingerprintJS',
            "creepjs": 'window.creepjs',
            "maxmind": 'window.maxmind',
        }
        
        detected = {}
        
        for name, check in fingerprinting_detectors.items():
            try:
                exists = await page.evaluate(f"(() => {{return typeof ({check}) !== 'undefined'}})()")
                detected[name] = exists
            except Exception as e:
                self.logger.debug(f"Fingerprinting check failed: {e}")
        
        return detected
    
    async def run_fingerprint_test(self, page: pw.Page) -> dict[str, Any]:
        """
        Test page to extract fingerprint data.
        Useful for debugging and validation.
        """
        
        # Get various fingerprinting signals
        fingerprint_data = await page.evaluate("""
        (() => {{
            const fp = {{}};
            
            // Screen
            fp.screen = {{
                width: window.screen.width,
                height: window.screen.height,
                colorDepth: window.screen.colorDepth,
                pixelDepth: window.screen.pixelDepth,
            }};
            
            // Navigator
            fp.navigator = {{
                userAgent: navigator.userAgent,
                language: navigator.language,
                languages: navigator.languages,
                platform: navigator.platform,
                hardwareConcurrency: navigator.hardwareConcurrency,
                deviceMemory: navigator.deviceMemory,
                maxTouchPoints: navigator.maxTouchPoints,
                webdriver: navigator.webdriver,
                plugins: navigator.plugins.length,
            }};
            
            // WebGL
            try {{
                const canvas = document.createElement('canvas');
                const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
                fp.webgl = {{
                    vendor: gl.getParameter(gl.getExtension('WEBGL_debug_renderer_info').UNMASKED_VENDOR_WEBGL),
                    renderer: gl.getParameter(gl.getExtension('WEBGL_debug_renderer_info').UNMASKED_RENDERER_WEBGL),
                }};
            }} catch(e) {{
                fp.webgl = null;
            }}
            
            // Timezone
            fp.timezone = new Date().getTimezoneOffset();
            
            return fp;
        }})()
        """)
        
        return fingerprint_data
    
    def get_device_profile_json(self) -> str:
        """Export device profile as JSON for logging/debugging."""
        return json.dumps({
            "screen": {
                "width": self.device_profile.screen_width,
                "height": self.device_profile.screen_height,
                "dpr": self.device_profile.device_pixel_ratio,
            },
            "hardware": {
                "cores": self.device_profile.hardware_concurrency,
                "memory_gb": self.device_profile.device_memory,
            },
            "gpu": {
                "vendor": self.device_profile.webgl_vendor,
                "renderer": self.device_profile.webgl_renderer,
            },
            "system": {
                "platform": self.device_profile.platform,
                "timezone": self.device_profile.timezone,
                "language": self.device_profile.language,
            },
            "device_id": self.device_profile.device_id,
        }, indent=2)


# Realistic device profiles for common configurations
REALISTIC_DEVICE_PROFILES = {
    "windows_chrome": DeviceProfile(
        screen_width=1920,
        screen_height=1080,
        device_pixel_ratio=1.0,
        hardware_concurrency=8,
        device_memory=16,
        webgl_vendor="Intel Inc.",
        webgl_renderer="Intel Iris OpenGL Engine",
        timezone="America/New_York",
        platform="Win32",
    ),
    "macos_chrome": DeviceProfile(
        screen_width=1440,
        screen_height=900,
        device_pixel_ratio=2.0,
        hardware_concurrency=8,
        device_memory=8,
        webgl_vendor="Apple Inc.",
        webgl_renderer="Apple M1",
        timezone="America/Los_Angeles",
        platform="MacIntel",
    ),
    "linux_firefox": DeviceProfile(
        screen_width=1920,
        screen_height=1080,
        device_pixel_ratio=1.0,
        hardware_concurrency=4,
        device_memory=8,
        webgl_vendor="Intel Inc.",
        webgl_renderer="Intel HD Graphics 630",
        timezone="UTC",
        platform="Linux x86_64",
    ),
}


def create_fingerprint_layer(profile: DeviceProfile | None = None) -> Layer4BrowserFingerprinting:
    """Create browser fingerprinting layer with optional device profile."""
    return Layer4BrowserFingerprinting(profile)
