"""
Patchright Integration - ★★ Playwright Fork with Enhanced Stealth
===================================================================
Patchright is a patched version of Playwright that removes the Runtime.enable
CDP command, significantly reducing the detection surface.

Key Differences from Playwright:
- Runtime.enable CDP command removed (major detection vector)
- ~67% stealth improvement over vanilla Playwright
- Additional stealth patches for CDP fingerprinting
- Drop-in replacement for Playwright

Power Ranking: ★★ (Strong binary-patch level stealth)
Detection Rate: ~33% (vs 100% for vanilla Playwright on aggressive detectors)

Reference: https://github.com/Kaliiiiiiiiii-Vinyzu/patchright
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, AsyncIterator, Optional

try:
    from patchright.async_api import async_playwright, Browser, BrowserContext, Page
    PATCHRIGHT_AVAILABLE = True
except ImportError:
    PATCHRIGHT_AVAILABLE = False
    async_playwright = None
    Browser = None
    BrowserContext = None
    Page = None

logger = logging.getLogger(__name__)


@dataclass
class PatchrightConfig:
    """Configuration for Patchright browser."""
    
    # Browser launch options
    headless: bool = True
    browser_type: str = "chromium"  # chromium, firefox, webkit
    
    # User agent and viewport
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
    viewport_width: int = 1920
    viewport_height: int = 1080
    device_scale_factor: float = 1.0
    
    # Stealth options
    disable_blink_features: bool = True  # Disable AutomationControlled
    mask_permissions: bool = True
    timezone_id: str = "America/New_York"
    locale: str = "en-US"
    
    # Network
    proxy_server: Optional[str] = None
    ignore_https_errors: bool = False
    
    # Timeouts
    timeout: int = 30000  # milliseconds
    
    # Additional args
    extra_args: list[str] = None
    
    def __post_init__(self):
        if self.extra_args is None:
            self.extra_args = []


class PatchrightBrowser:
    """
    Wrapper for Patchright browser with enhanced stealth.
    
    Patchright is a drop-in replacement for Playwright with Runtime.enable
    CDP command removed, making it significantly harder to detect.
    """
    
    def __init__(self, config: PatchrightConfig = PatchrightConfig()):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self.last_status_code = 0
        self.last_final_url = ""
        
        if not PATCHRIGHT_AVAILABLE:
            self.logger.warning(
                "Patchright not installed. Install with: pip install patchright && patchright install"
            )
    
    async def start(self) -> bool:
        """
        Start Patchright browser.
        
        Returns:
            True if successful
        """
        
        if not PATCHRIGHT_AVAILABLE:
            self.logger.error("Patchright not available")
            return False
        
        try:
            # Start Playwright
            self._playwright = await async_playwright().start()
            
            # Get browser type
            if self.config.browser_type == "chromium":
                browser_type = self._playwright.chromium
            elif self.config.browser_type == "firefox":
                browser_type = self._playwright.firefox
            elif self.config.browser_type == "webkit":
                browser_type = self._playwright.webkit
            else:
                self.logger.error(f"Unknown browser type: {self.config.browser_type}")
                return False
            
            # Build launch arguments
            launch_args = []
            
            if self.config.disable_blink_features:
                launch_args.append("--disable-blink-features=AutomationControlled")
            
            # Add extra args
            launch_args.extend(self.config.extra_args)
            
            # Launch browser
            self._browser = await browser_type.launch(
                headless=self.config.headless,
                args=launch_args if launch_args else None,
            )
            
            # Create context with stealth settings
            context_options = {
                "user_agent": self.config.user_agent,
                "viewport": {
                    "width": self.config.viewport_width,
                    "height": self.config.viewport_height,
                },
                "device_scale_factor": self.config.device_scale_factor,
                "locale": self.config.locale,
                "timezone_id": self.config.timezone_id,
                "ignore_https_errors": self.config.ignore_https_errors,
            }
            
            # Add proxy if configured
            if self.config.proxy_server:
                context_options["proxy"] = {"server": self.config.proxy_server}
            
            # Add permissions masking
            if self.config.mask_permissions:
                context_options["permissions"] = []
            
            self._context = await self._browser.new_context(**context_options)
            
            # Apply additional stealth scripts
            await self._apply_stealth_scripts()
            
            self.logger.info("✓ Patchright browser started with enhanced stealth")
            return True
        
        except Exception as e:
            self.logger.error(f"Failed to start Patchright browser: {e}")
            return False
    
    async def _apply_stealth_scripts(self) -> None:
        """Apply additional stealth JavaScript patches."""
        
        if not self._context:
            return
        
        # Stealth script to further reduce detection surface
        stealth_script = """
        // Remove webdriver property
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        });
        
        // Add chrome runtime
        window.chrome = {
            runtime: {}
        };
        
        // Override permissions
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => (
            parameters.name === 'notifications' ?
                Promise.resolve({ state: Notification.permission }) :
                originalQuery(parameters)
        );
        
        // Consistent plugins
        Object.defineProperty(navigator, 'plugins', {
            get: () => [
                {
                    name: 'Chrome PDF Plugin',
                    description: 'Portable Document Format',
                    filename: 'internal-pdf-viewer'
                },
                {
                    name: 'Chrome PDF Viewer',
                    description: '',
                    filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai'
                }
            ]
        });
        """
        
        await self._context.add_init_script(stealth_script)
    
    async def new_page(self) -> Optional[Page]:
        """
        Create new page in browser context.
        
        Returns:
            Page object or None
        """
        
        if not self._context:
            self.logger.error("Browser context not initialized")
            return None
        
        try:
            page = await self._context.new_page()
            
            # Set default timeout
            page.set_default_timeout(self.config.timeout)
            
            return page
        
        except Exception as e:
            self.logger.error(f"Failed to create page: {e}")
            return None
    
    async def navigate(self, url: str) -> tuple[bool, str]:
        """
        Navigate to URL and get HTML content.
        
        Args:
            url: Target URL
        
        Returns:
            Tuple of (success, html_content)
        """
        
        page = await self.new_page()
        if not page:
            return False, ""
        self.last_status_code = 0
        self.last_final_url = url
        
        try:
            # Navigate to URL
            response = await page.goto(url, wait_until="domcontentloaded")
            
            # Wait for network idle
            await page.wait_for_load_state("networkidle", timeout=min(10000, self.config.timeout))
            
            # Get HTML
            html = await page.content()
            status = response.status if response else 0
            final_url = page.url
            
            # Close page
            await page.close()
            
            self.last_status_code = status
            self.last_final_url = final_url
            self.logger.info(f"✓ Navigated to {url} (status: {status})")
            
            return True, html
        
        except Exception as e:
            self.logger.error(f"Navigation failed: {e}")
            
            try:
                await page.close()
            except:
                pass
            
            return False, ""
    
    @asynccontextmanager
    async def get_page(self) -> AsyncIterator[Page]:
        """
        Context manager for getting a page.
        
        Usage:
            async with browser.get_page() as page:
                await page.goto("https://example.com")
        """
        
        page = await self.new_page()
        if not page:
            raise RuntimeError("Failed to create page")
        
        try:
            yield page
        finally:
            await page.close()
    
    async def close(self) -> None:
        """Close browser and cleanup."""
        
        if self._context:
            try:
                await self._context.close()
            except Exception as e:
                self.logger.error(f"Context close failed: {e}")
        
        if self._browser:
            try:
                await self._browser.close()
            except Exception as e:
                self.logger.error(f"Browser close failed: {e}")
        
        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception as e:
                self.logger.error(f"Playwright stop failed: {e}")
        
        self._context = None
        self._browser = None
        self._playwright = None
        
        self.logger.info("✓ Patchright browser closed")
    
    def is_available(self) -> bool:
        """Check if Patchright is available."""
        return PATCHRIGHT_AVAILABLE
    
    def get_status(self) -> dict[str, Any]:
        """Get status information."""
        
        return {
            "framework": "patchright",
            "available": PATCHRIGHT_AVAILABLE,
            "running": self._browser is not None,
            "stealth_level": "★★ (binary-patch)",
            "detection_rate": "~33% (vs 100% vanilla Playwright)",
            "key_patches": [
                "Runtime.enable removed",
                "CDP fingerprint reduced",
                "Additional JS stealth patches",
            ],
            "features": {
                "playwright_compatible": True,
                "headless_support": True,
                "proxy_support": True,
                "multi_browser": True,
            }
        }


class PatchrightPool:
    """
    Pool of Patchright browser instances.
    """
    
    def __init__(self, pool_size: int = 4, config: PatchrightConfig = PatchrightConfig()):
        self.pool_size = pool_size
        self.config = config
        self.browsers: list[PatchrightBrowser] = []
        self.semaphore = asyncio.Semaphore(pool_size)
        self.logger = logging.getLogger(__name__)
    
    async def initialize(self) -> None:
        """Initialize browser pool."""
        
        self.logger.info(f"Initializing Patchright pool with {self.pool_size} browsers")
        
        for i in range(self.pool_size):
            browser = PatchrightBrowser(self.config)
            success = await browser.start()
            
            if success:
                self.browsers.append(browser)
            else:
                self.logger.warning(f"Failed to start browser {i+1}/{self.pool_size}")
        
        self.logger.info(f"✓ Patchright pool initialized: {len(self.browsers)}/{self.pool_size} browsers")
    
    async def render(self, url: str) -> tuple[bool, str]:
        """
        Render URL using pool.
        
        Args:
            url: Target URL
        
        Returns:
            Tuple of (success, html_content)
        """
        
        async with self.semaphore:
            if not self.browsers:
                self.logger.error("No browsers available in pool")
                return False, ""
            
            # Round-robin browser selection
            browser = self.browsers[0]
            
            # Rotate browsers
            self.browsers.append(self.browsers.pop(0))
            
            return await browser.navigate(url)
    
    async def close_all(self) -> None:
        """Close all browsers in pool."""
        
        for browser in self.browsers:
            await browser.close()
        
        self.browsers.clear()
        self.logger.info("✓ All Patchright browsers closed")


# Factory functions
def create_patchright_browser(config: PatchrightConfig = PatchrightConfig()) -> PatchrightBrowser:
    """Create Patchright browser instance."""
    return PatchrightBrowser(config)


def create_patchright_pool(pool_size: int = 4, config: PatchrightConfig = PatchrightConfig()) -> PatchrightPool:
    """Create Patchright browser pool."""
    return PatchrightPool(pool_size, config)


# Integration check
def is_patchright_available() -> bool:
    """Check if Patchright is installed and available."""
    return PATCHRIGHT_AVAILABLE


def get_patchright_info() -> dict[str, Any]:
    """Get Patchright library information."""
    
    info = {
        "library": "patchright",
        "installed": PATCHRIGHT_AVAILABLE,
        "power_rating": "★★",
        "detection_rate": "~33% (significant improvement over vanilla Playwright)",
        "key_advantage": "Runtime.enable CDP command removed",
        "advantages": [
            "Binary-patch level stealth",
            "Drop-in Playwright replacement",
            "Runtime.enable removed",
            "Reduced CDP fingerprint",
            "Playwright API compatibility",
        ],
        "use_cases": [
            "When Playwright is detected",
            "CDP fingerprinting concern",
            "Need Playwright API + stealth",
        ],
        "installation": "pip install patchright && patchright install"
    }
    
    if PATCHRIGHT_AVAILABLE:
        try:
            import patchright
            info["version"] = patchright.__version__
        except:
            pass
    
    return info
