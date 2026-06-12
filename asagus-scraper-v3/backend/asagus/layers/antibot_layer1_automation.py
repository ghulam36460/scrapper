"""
Layer 1: Core Automation Frameworks
====================================
Intelligent framework selection based on target site characteristics.
Chooses between: Browser-based (CDP) vs HTTP-only automation.

Key Insight from antibot.md:
- Browser automation (Playwright, Puppeteer, nodriver) needed for:
  - JavaScript-rendered content
  - CAPTCHA solving
  - Complex browser interactions
  - Behavioral analysis sites

- HTTP-only automation (curl-cffi, httpx, Scrapy) needed for:
  - Server-rendered HTML
  - API endpoints
  - 10-50x faster, lower resource usage
  - Smaller detection surface

Decision Rule: Only use browser when JavaScript rendering is REQUIRED.
Most common mistake: Using full browser when HTTP-only would suffice.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Literal

import httpx
import playwright.async_api as pw


logger = logging.getLogger(__name__)


class AutomationFramework(Enum):
    """Core automation framework types."""
    # Browser-based (CDP/WebDriver)
    playwright = "playwright"  # ★★★ Modern, fast, CDP-based
    puppeteer = "puppeteer"    # JavaScript/Node.js only
    selenium = "selenium"      # Legacy, all browsers, WebDriver
    nodriver = "nodriver"      # ★★★ Minimal CDP, wins protocol benchmarks
    
    # HTTP-only
    curl_cffi = "curl_cffi"    # ★★★ Built-in TLS impersonation, fastest
    httpx = "httpx"            # Async HTTP/1+2, pair with TLS tools
    scrapy = "scrapy"          # Large-scale HTTP crawling
    mechanize = "mechanize"    # Old-school, browser-like HTTP


class JSRequirement(Enum):
    """JavaScript requirement detection."""
    required = "required"          # JavaScript execution necessary
    optional = "optional"          # JavaScript helpful but not required
    not_required = "not_required"  # Pure HTML/API sufficient


@dataclass
class FrameworkSelectionCriteria:
    """Criteria for choosing optimal framework."""
    url: str
    requires_js: JSRequirement = JSRequirement.optional
    requires_captcha_solve: bool = False
    requires_browser_interaction: bool = False
    requires_behavioral_analysis: bool = False
    needs_high_throughput: bool = False
    available_memory_mb: int = 2048
    latency_tolerance_seconds: float = 10.0
    priority: Literal["speed", "stealth", "compatibility"] = "stealth"


@dataclass
class FrameworkConfig:
    """Configuration for selected framework."""
    framework: AutomationFramework
    user_agent: str
    viewport_width: int = 1365
    viewport_height: int = 900
    timeout_ms: int = 30_000
    proxy_url: str = ""
    
    # Browser-specific
    headless: bool = True
    disable_images: bool = False  # Set True for Layer 2 stealth
    disable_blink_features: str = ""  # Disable CDP detection features
    
    # TLS-specific (for curl-cffi)
    tls_ja3_client: str = "Chrome124Windows"  # Will be set by Layer 3
    
    # Stealth (set by Layer 2)
    use_stealth_mode: bool = True
    use_puppeteer_stealth_plugin: bool = False
    use_patchright: bool = False


class Layer1AutomationSelector:
    """Intelligent framework selection and factory."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
    def select_framework(self, criteria: FrameworkSelectionCriteria) -> FrameworkConfig:
        """
        Select optimal automation framework based on criteria.
        
        Decision matrix:
        ┌─────────────────────────────────────────────────────────────┐
        │ JS Required?  │ CAPTCHA?  │ Throughput? → Framework         │
        ├─────────────────────────────────────────────────────────────┤
        │ Yes           │ Yes       │ Any        → playwright/nodriver │
        │ Yes           │ No        │ High       → nodriver (min CDP)  │
        │ Yes           │ No        │ Normal     → playwright         │
        │ No            │ N/A       │ High       → curl-cffi + TLS    │
        │ No            │ N/A       │ Normal     → httpx + TLS        │
        └─────────────────────────────────────────────────────────────┘
        """
        
        # Tier 1: If JavaScript is definitely required
        if criteria.requires_js == JSRequirement.required:
            if criteria.requires_captcha_solve:
                # Need full CDP for CAPTCHA interaction
                framework = AutomationFramework.playwright
                self.logger.info(f"Selected {framework} for JS + CAPTCHA solving")
            elif criteria.needs_high_throughput:
                # Minimal CDP overhead (nodriver wins benchmarks)
                framework = AutomationFramework.nodriver
                self.logger.info(f"Selected {framework} for minimal CDP signature")
            else:
                # Standard browser automation
                framework = AutomationFramework.playwright
                self.logger.info(f"Selected {framework} for standard browser automation")
        
        # Tier 2: If JavaScript is optional/not required
        else:
            if criteria.needs_high_throughput or criteria.available_memory_mb < 1024:
                # Pure HTTP with TLS impersonation - 10-50x faster
                framework = AutomationFramework.curl_cffi
                self.logger.info(f"Selected {framework} for high-throughput HTTP scraping")
            else:
                # Standard async HTTP
                framework = AutomationFramework.httpx
                self.logger.info(f"Selected {framework} for standard HTTP scraping")
        
        return FrameworkConfig(
            framework=framework,
            user_agent=self._get_user_agent_for_framework(framework, criteria),
            proxy_url=criteria.__dict__.get("proxy_url", ""),
        )
    
    def _get_user_agent_for_framework(self, framework: AutomationFramework, 
                                       criteria: FrameworkSelectionCriteria) -> str:
        """Get realistic User-Agent for framework."""
        # Layer 3 will handle TLS fingerprint matching
        
        ua_map = {
            AutomationFramework.playwright: (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            AutomationFramework.puppeteer: (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            AutomationFramework.nodriver: (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            AutomationFramework.selenium: (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            AutomationFramework.curl_cffi: (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            AutomationFramework.httpx: (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            AutomationFramework.scrapy: (
                "Scrapy/2.11 (+https://scrapy.org)"
            ),
            AutomationFramework.mechanize: (
                "Python-mechanize/5.0"
            ),
        }
        
        return ua_map.get(framework, "Mozilla/5.0")
    
    async def create_http_client(self, config: FrameworkConfig) -> httpx.AsyncClient:
        """Create configured HTTP client (curl-cffi or httpx)."""
        
        kwargs = {
            "headers": {
                "User-Agent": config.user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            },
            "timeout": config.timeout_ms / 1000,
        }
        
        if config.proxy_url:
            kwargs["proxies"] = config.proxy_url
        
        # For curl-cffi, Layer 3 will inject TLS impersonation
        # For httpx, pair with tls-client or other TLS library
        
        return httpx.AsyncClient(**kwargs)
    
    async def create_browser_context(self, config: FrameworkConfig) -> dict[str, Any]:
        """Create configured browser context for Playwright/Selenium."""
        
        context_options = {
            "user_agent": config.user_agent,
            "viewport": {"width": config.viewport_width, "height": config.viewport_height},
            "java_script_enabled": True,
        }
        
        if config.proxy_url:
            context_options["proxy"] = {"server": config.proxy_url}
        
        # Layer 2 will inject stealth modifications
        # Layer 4 will handle fingerprint consistency
        
        return context_options
    
    def analyze_target_site(self, url: str) -> JSRequirement:
        """
        Heuristic analysis of target site to detect JS requirement.
        
        In production, this would:
        1. Fetch initial HTML
        2. Check for:
           - SPA frameworks (React, Vue, Angular markers)
           - JSON responses (API endpoint)
           - SSR indicators (Next.js, Nuxt markers)
           - JavaScript-heavy indicators
        """
        
        # Simplified heuristic
        if any(api_indicator in url for api_indicator in ["/api/", ".json", "/graphql", "/rest/"]):
            return JSRequirement.not_required
        
        if any(spa_indicator in url for spa_indicator in ["app.", "admin.", "dashboard.", "portal."]):
            return JSRequirement.required
        
        return JSRequirement.optional


# Singleton instance
_automation_selector = Layer1AutomationSelector()


def get_framework_selector() -> Layer1AutomationSelector:
    """Get singleton framework selector."""
    return _automation_selector
