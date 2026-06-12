"""
Layer 2: Stealth and Anti-Detection Patching
=============================================
Removes signals that identify browser automation.

Two Fundamental Approaches:
1. JavaScript-Shim Level (Weaker)
   - Inject JS into every page before execution
   - Patch navigator.webdriver, chrome.runtime, etc.
   - Limitation: Modern detectors check prototype chain, V8 bytecode
   - Tools: puppeteer-extra-stealth, playwright-stealth

2. Binary-Patch Level (Stronger) ★★★
   - Modify browser source code at C++ level
   - Remove headless detection signals at compile time
   - Prevents "lie detection" - nothing to lie about
   - Tools: Camoufox (0% detection), CloakBrowser, Patchright (67% CreepJS)

Reference from antibot.md:
Layer 2 targets these signals:
- navigator.webdriver (set to undefined)
- chrome.runtime (recreated)
- navigator.plugins (fake entries)
- window.chrome (added)
- Permissions API (realistic defaults)
- WebGL renderer (SwiftShader→real GPU string)
- V8 internal state consistency
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

import playwright.async_api as pw


logger = logging.getLogger(__name__)


class StealthApproach(Enum):
    """Stealth patching methodology."""
    javascript_shim = "javascript_shim"      # JS-level patching (weaker)
    binary_patch = "binary_patch"            # C++ binary patching (★★★ strongest)
    patchright = "patchright"                # Playwright Runtime.enable removal
    camoufox = "camoufox"                    # Firefox C++ fork (0% detection)
    cloak_browser = "cloak_browser"          # Chromium C++ fork (new 2026)
    undetected_chromedriver = "undetected_chromedriver"  # ChromeDriver patch


@dataclass
class StealthConfig:
    """Configuration for stealth patching."""
    approach: StealthApproach = StealthApproach.javascript_shim
    
    # JavaScript shim patches to apply
    patch_navigator_webdriver: bool = True
    patch_chrome_runtime: bool = True
    patch_navigator_plugins: bool = True
    patch_window_chrome: bool = True
    patch_permissions_api: bool = True
    patch_webgl_renderer: bool = True
    patch_audio_context: bool = False  # Expensive, Layer 4 handles
    
    # Binary-patch configuration
    use_patchright: bool = False  # Removes CDP Runtime.enable
    use_camoufox: bool = False    # Use Camoufox binary (Firefox)
    use_cloak_browser: bool = False  # Use CloakBrowser binary (Chromium)
    
    # General options
    disable_images: bool = False  # Reduce fingerprinting surface
    disable_webgl: bool = False   # Disable if not needed
    disable_webrtc: bool = True   # Prevent IP leak
    headless: bool = True


class Layer2StealthPatching:
    """Apply stealth patches to prevent automation detection."""
    
    def __init__(self, config: StealthConfig = StealthConfig()):
        self.config = config
        self.logger = logging.getLogger(__name__)
    
    async def apply_stealth_to_context(self, context: pw.BrowserContext) -> None:
        """Apply stealth patches to browser context."""
        
        if self.config.approach == StealthApproach.javascript_shim:
            await self._apply_javascript_shim(context)
        elif self.config.approach == StealthApproach.patchright:
            await self._apply_patchright_patches(context)
        # Binary patches (Camoufox, CloakBrowser) require different browser launch
    
    async def _apply_javascript_shim(self, context: pw.BrowserContext) -> None:
        """Apply comprehensive JavaScript stealth patches."""
        
        # Inject script into every page before anything else
        init_script = self._generate_stealth_script()
        await context.add_init_script(init_script)
        self.logger.info("Applied JavaScript stealth patches to context")
    
    def _generate_stealth_script(self) -> str:
        """Generate comprehensive JavaScript stealth script."""
        
        patches = []
        
        # Patch 1: navigator.webdriver
        if self.config.patch_navigator_webdriver:
            patches.append("""
            // Remove navigator.webdriver
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            """)
        
        # Patch 2: chrome.runtime
        if self.config.patch_chrome_runtime:
            patches.append("""
            // Create chrome.runtime object
            window.chrome = {
                runtime: {}
            };
            """)
        
        # Patch 3: navigator.plugins
        if self.config.patch_navigator_plugins:
            patches.append("""
            // Populate navigator.plugins with realistic entries
            const fakePlugins = [
                {
                    name: 'Chrome PDF Plugin',
                    description: 'Portable Document Format',
                    filename: 'internal-pdf-viewer',
                    version: ''
                },
                {
                    name: 'Chrome PDF Viewer',
                    description: '',
                    filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai',
                    version: ''
                }
            ];
            
            Object.defineProperty(navigator, 'plugins', {
                get: () => fakePlugins
            });
            """)
        
        # Patch 4: window.chrome properties
        if self.config.patch_window_chrome:
            patches.append("""
            // Ensure window.chrome exists and has realistic properties
            if (!window.chrome) window.chrome = {};
            window.chrome.runtime = window.chrome.runtime || {};
            """)
        
        # Patch 5: Permissions API
        if self.config.patch_permissions_api:
            patches.append("""
            // Override Permissions API
            const originalQuery = navigator.permissions.query;
            navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
            """)
        
        # Patch 6: WebGL renderer string
        if self.config.patch_webgl_renderer:
            patches.append("""
            // Patch WebGL renderer - prevent SwiftShader detection
            const getParameter = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(parameter) {
                if (parameter === 37445) {  // UNMASKED_VENDOR_WEBGL
                    return 'Intel Inc.';
                }
                if (parameter === 37446) {  // UNMASKED_RENDERER_WEBGL
                    return 'Intel Iris OpenGL Engine';
                }
                return getParameter.call(this, parameter);
            };
            """)
        
        # Patch 7: Prevent CDP detection via error stack
        patches.append("""
            // Prevent CDP detection via Error.stack
            const originalPrepareStackTrace = Error.prepareStackTrace;
            Error.prepareStackTrace = function(error, structuredStackTrace) {
                return structuredStackTrace.filter(callSite => {
                    const functionName = callSite.getFunctionName() || '';
                    return !functionName.includes('devtools');
                }).map(callSite => callSite.toString()).join('\\n');
            };
            if (originalPrepareStackTrace) {
                Error.prepareStackTrace = originalPrepareStackTrace;
            }
        """)
        
        # Combine all patches
        return "\n".join(patches)
    
    async def _apply_patchright_patches(self, context: pw.BrowserContext) -> None:
        """Apply Patchright-style patches (removes Runtime.enable CDP command)."""
        
        # Patchright works at Playwright level by removing CDP Runtime.enable
        # This significantly reduces protocol-level detection surface
        
        init_script = self._generate_stealth_script()
        await context.add_init_script(init_script)
        
        self.logger.info("Applied Patchright-style patches (minimal CDP)")
    
    def get_launch_options_for_binary_patch(self, approach: StealthApproach) -> dict[str, Any]:
        """Get browser launch options for binary-patch approaches."""
        
        options = {
            "headless": self.config.headless,
            "args": []
        }
        
        if approach == StealthApproach.camoufox:
            # Camoufox is a Firefox fork - C++ source modification
            # No additional launch args needed - binary is already patched
            options["executable_path"] = "/usr/bin/camoufox"  # Path varies
            self.logger.info("Using Camoufox (Firefox C++ fork) - 0% headless detection")
        
        elif approach == StealthApproach.cloak_browser:
            # CloakBrowser is a Chromium fork - 49+ binary patches
            options["executable_path"] = "/usr/bin/cloak-browser"  # Path varies
            self.logger.info("Using CloakBrowser (Chromium C++ fork) - very low detection")
        
        elif approach == StealthApproach.undetected_chromedriver:
            # undetected-chromedriver patches ChromeDriver binary
            # Launch via undetected_chromedriver module
            pass
        
        # Common stealth args
        options["args"].extend([
            "--disable-blink-features=AutomationControlled",
            "--start-maximized",
        ])
        
        if self.config.disable_webrtc:
            options["args"].append("--disable-features=IsolateOrigins,site-per-process")
        
        return options
    
    async def inject_stealth_headers(self, client: Any) -> None:
        """Inject stealth HTTP headers into client."""
        
        stealth_headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Cache-Control": "max-age=0",
        }
        
        # For httpx or requests client
        if hasattr(client, "headers"):
            client.headers.update(stealth_headers)
    
    def create_realistic_navigator_object(self) -> dict[str, Any]:
        """Create realistic navigator object for HTTP clients."""
        
        return {
            "userAgent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "language": "en-US",
            "languages": ["en-US", "en"],
            "platform": "Win32",
            "hardwareConcurrency": 8,
            "deviceMemory": 8,
            "maxTouchPoints": 0,
        }


# Factory function for creating stealth layer with recommended config
def create_stealth_layer(approach: StealthApproach = StealthApproach.javascript_shim) -> Layer2StealthPatching:
    """Create stealth layer with recommended configuration."""
    
    config = StealthConfig(approach=approach)
    
    # Recommendations from antibot.md 2026 benchmark
    if approach == StealthApproach.camoufox:
        # Camoufox: ★★★ Best OSS stealth (0% headless detection)
        config.use_camoufox = True
    elif approach == StealthApproach.cloak_browser:
        # CloakBrowser: ★★★ Strong new entry (new 2026)
        config.use_cloak_browser = True
    elif approach == StealthApproach.patchright:
        # Patchright: ★★ Removes Runtime.enable CDP command (~67% stealth)
        config.use_patchright = True
    
    return Layer2StealthPatching(config)
