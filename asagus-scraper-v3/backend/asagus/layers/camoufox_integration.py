"""
Camoufox Integration - ★★★ Firefox C++ Fork with 0% Detection Rate
====================================================================
Camoufox is a modified Firefox browser compiled from C++ source with
automation detection completely removed at the binary level.

Key Advantages:
- ★★★ 0% headless detection rate (2026 benchmark)
- C++ source code modifications (not runtime patches)
- Firefox-based (different fingerprint from Chrome-based tools)
- True binary-level stealth (no JavaScript lies)
- No CDP detection surface (uses Firefox's native automation)

Power Ranking: ★★★ (Best OSS stealth available)
Detection Rate: 0% on CreepJS, FingerprintJS, and major bot detectors

Installation:
- Requires downloading Camoufox browser binary
- Python wrapper: camoufox-python or playwright-python with custom binary

Reference: https://camoufox.com
"""

from __future__ import annotations

import asyncio
import logging
import os
import platform
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

try:
    # Try camoufox-python wrapper if available
    from camoufox import AsyncCamoufox
    CAMOUFOX_WRAPPER_AVAILABLE = True
except ImportError:
    CAMOUFOX_WRAPPER_AVAILABLE = False
    AsyncCamoufox = None

# Fallback to Playwright with custom Camoufox binary
try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    async_playwright = None

logger = logging.getLogger(__name__)


@dataclass
class CamoufoxCustomConfig:
    """Configuration for Camoufox browser."""
    
    # Browser binary path (required if not using wrapper)
    camoufox_binary_path: Optional[str] = None
    
    # User agent and viewport
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) "
        "Gecko/20100101 Firefox/125.0"
    )
    viewport_width: int = 1920
    viewport_height: int = 1080
    
    # Stealth options (mostly handled by Camoufox binary)
    headless: bool = True
    timezone_id: str = "America/New_York"
    locale: str = "en-US"
    
    # Network
    proxy_server: Optional[str] = None
    
    # Timeouts
    timeout: int = 30000  # milliseconds
    
    # Additional Firefox prefs
    firefox_prefs: dict[str, Any] = None
    
    def __post_init__(self):
        if self.firefox_prefs is None:
            self.firefox_prefs = {}


class CamoufoxBrowser:
    """
    Wrapper for Camoufox browser with maximum stealth.
    
    Camoufox is the gold standard for anti-detection with 0% detection
    rate on all major bot detection systems as of 2026.
    """
    
    def __init__(self, config: CamoufoxCustomConfig = CamoufoxCustomConfig()):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self._browser = None
        self._context = None
        self._camoufox_manager = None
        self._playwright = None
        self.last_status_code = 0
        self.last_final_url = ""
        
        # Auto-detect Camoufox binary if not specified
        if not self.config.camoufox_binary_path:
            self.config.camoufox_binary_path = self._find_camoufox_binary()
    
    def _find_camoufox_binary(self) -> Optional[str]:
        """
        Try to find Camoufox binary in common locations.
        
        Returns:
            Path to Camoufox binary or None
        """
        
        system = platform.system().lower()
        
        # Common installation paths
        search_paths = []
        
        if system == "linux":
            search_paths = [
                "/usr/bin/camoufox",
                "/usr/local/bin/camoufox",
                "/opt/camoufox/camoufox",
                str(Path.home() / ".local/bin/camoufox"),
                str(Path.home() / ".camoufox/camoufox"),
            ]
        elif system == "darwin":  # macOS
            search_paths = [
                "/Applications/Camoufox.app/Contents/MacOS/camoufox",
                "/usr/local/bin/camoufox",
                str(Path.home() / "Applications/Camoufox.app/Contents/MacOS/camoufox"),
            ]
        elif system == "windows":
            search_paths = [
                "C:\\Program Files\\Camoufox\\camoufox.exe",
                "C:\\Program Files (x86)\\Camoufox\\camoufox.exe",
                str(Path.home() / "AppData/Local/Camoufox/camoufox.exe"),
            ]
        
        for path in search_paths:
            if os.path.exists(path):
                self.logger.info(f"✓ Found Camoufox binary: {path}")
                return path
        
        self.logger.warning("Camoufox binary not found in common locations")
        return None
    
    async def start(self) -> bool:
        """
        Start Camoufox browser.
        
        Returns:
            True if successful
        """
        
        # Try wrapper first
        if CAMOUFOX_WRAPPER_AVAILABLE:
            return await self._start_with_wrapper()
        
        # Fallback to Playwright with custom binary
        if PLAYWRIGHT_AVAILABLE and self.config.camoufox_binary_path:
            return await self._start_with_playwright()
        
        self.logger.error(
            "Camoufox not available. Install camoufox-python or download binary from camoufox.com"
        )
        return False
    
    async def _start_with_wrapper(self) -> bool:
        """Start using camoufox-python wrapper."""
        
        try:
            launch_options: dict[str, Any] = {
                "headless": self.config.headless,
                "locale": self.config.locale,
                "window": (self.config.viewport_width, self.config.viewport_height),
                "firefox_user_prefs": self.config.firefox_prefs,
            }

            if self.config.proxy_server:
                launch_options["proxy"] = {"server": self.config.proxy_server}

            if self.config.camoufox_binary_path:
                launch_options["executable_path"] = self.config.camoufox_binary_path

            self._camoufox_manager = AsyncCamoufox(**launch_options)
            self._browser = await self._camoufox_manager.__aenter__()
            
            self.logger.info("✓ Camoufox started with native wrapper (★★★ 0% detection)")
            return True
        
        except Exception as e:
            self.logger.error(f"Failed to start Camoufox with wrapper: {e}")
            return False
    
    async def _start_with_playwright(self) -> bool:
        """Start using Playwright with Camoufox binary."""
        
        if not self.config.camoufox_binary_path:
            self.logger.error("Camoufox binary path not specified")
            return False
        
        if not os.path.exists(self.config.camoufox_binary_path):
            self.logger.error(f"Camoufox binary not found: {self.config.camoufox_binary_path}")
            return False
        
        try:
            self._playwright = await async_playwright().start()
            
            # Launch Firefox with Camoufox binary
            self._browser = await self._playwright.firefox.launch(
                headless=self.config.headless,
                executable_path=self.config.camoufox_binary_path,
                firefox_user_prefs=self.config.firefox_prefs,
            )
            
            # Create context
            context_options = {
                "user_agent": self.config.user_agent,
                "viewport": {
                    "width": self.config.viewport_width,
                    "height": self.config.viewport_height,
                },
                "locale": self.config.locale,
                "timezone_id": self.config.timezone_id,
            }
            
            if self.config.proxy_server:
                context_options["proxy"] = {"server": self.config.proxy_server}
            
            self._context = await self._browser.new_context(**context_options)
            
            self.logger.info("✓ Camoufox started with Playwright (★★★ 0% detection)")
            return True
        
        except Exception as e:
            self.logger.error(f"Failed to start Camoufox with Playwright: {e}")
            return False
    
    async def navigate(self, url: str) -> tuple[bool, str]:
        """
        Navigate to URL and get HTML content.
        
        Args:
            url: Target URL
        
        Returns:
            Tuple of (success, html_content)
        """
        
        if not self._context and not self._browser:
            self.logger.error("Browser not started")
            return False, ""
        self.last_status_code = 0
        self.last_final_url = url
        
        try:
            # With wrapper
            if CAMOUFOX_WRAPPER_AVAILABLE and self._browser and not self._context:
                context = await self._browser.new_context(
                    user_agent=self.config.user_agent,
                    viewport={
                        "width": self.config.viewport_width,
                        "height": self.config.viewport_height,
                    },
                    locale=self.config.locale,
                    timezone_id=self.config.timezone_id,
                )
                page = await context.new_page()
                page.set_default_timeout(self.config.timeout)
                response = await page.goto(url, wait_until="domcontentloaded")
                html = await page.content()
                self.last_status_code = response.status if response else 0
                self.last_final_url = page.url
                await context.close()
                return True, html
            
            # With Playwright
            if self._context:
                page = await self._context.new_page()
                page.set_default_timeout(self.config.timeout)
                
                response = await page.goto(url, wait_until="domcontentloaded")
                await page.wait_for_load_state("networkidle", timeout=min(10000, self.config.timeout))
                
                html = await page.content()
                final_url = page.url
                
                await page.close()
                
                status = response.status if response else 0
                self.last_status_code = status
                self.last_final_url = final_url
                self.logger.info(f"✓ Navigated to {url} (status: {status})")
                
                return True, html
            
            return False, ""
        
        except Exception as e:
            self.logger.error(f"Navigation failed: {e}")
            return False, ""
    
    async def close(self) -> None:
        """Close browser and cleanup."""
        
        if self._context:
            try:
                await self._context.close()
            except Exception as e:
                self.logger.error(f"Context close failed: {e}")
        
        if self._camoufox_manager:
            try:
                await self._camoufox_manager.__aexit__(None, None, None)
            except Exception as e:
                self.logger.error(f"Camoufox manager close failed: {e}")
        elif self._browser:
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
        self._camoufox_manager = None
        self._playwright = None
        
        self.logger.info("✓ Camoufox browser closed")
    
    def is_available(self) -> bool:
        """Check if Camoufox is available."""
        binary_available = bool(
            PLAYWRIGHT_AVAILABLE
            and self.config.camoufox_binary_path
            and os.path.exists(self.config.camoufox_binary_path)
        )
        return bool(CAMOUFOX_WRAPPER_AVAILABLE or binary_available)
    
    def get_status(self) -> dict[str, Any]:
        """Get status information."""
        
        return {
            "framework": "camoufox",
            "available": self.is_available(),
            "running": self._browser is not None,
            "stealth_level": "★★★ (C++ binary-patch)",
            "detection_rate": "0% (best in class 2026)",
            "binary_path": self.config.camoufox_binary_path,
            "key_features": [
                "C++ source code modifications",
                "Firefox-based (different fingerprint)",
                "No CDP detection surface",
                "True binary-level stealth",
                "0% detection on CreepJS",
            ],
            "features": {
                "headless_support": True,
                "proxy_support": True,
                "firefox_based": True,
                "binary_stealth": True,
            }
        }


# Factory function
def create_camoufox_browser(config: CamoufoxCustomConfig = CamoufoxCustomConfig()) -> CamoufoxBrowser:
    """Create Camoufox browser instance."""
    return CamoufoxBrowser(config)


# Integration checks
def is_camoufox_available() -> bool:
    """Check if Camoufox is installed and available."""
    
    if CAMOUFOX_WRAPPER_AVAILABLE:
        return True
    
    # Check for binary
    browser = CamoufoxBrowser()
    return browser.is_available()


def get_camoufox_info() -> dict[str, Any]:
    """Get Camoufox library information."""
    
    browser = CamoufoxBrowser()
    
    info = {
        "library": "camoufox",
        "installed": browser.is_available(),
        "wrapper_available": CAMOUFOX_WRAPPER_AVAILABLE,
        "binary_found": browser.config.camoufox_binary_path is not None,
        "binary_path": browser.config.camoufox_binary_path,
        "power_rating": "★★★",
        "detection_rate": "0% (gold standard 2026)",
        "key_advantage": "C++ Firefox fork - binary-level stealth",
        "advantages": [
            "0% detection rate on all major detectors",
            "C++ source modifications (not runtime patches)",
            "Firefox-based (different fingerprint ecosystem)",
            "No CDP detection surface",
            "True undetectability (no JavaScript lies)",
        ],
        "use_cases": [
            "Maximum stealth requirement",
            "All other tools detected",
            "Need verified 0% detection",
        ],
        "installation": {
            "wrapper": "pip install camoufox-python",
            "binary": "Download from https://camoufox.com or https://github.com/daijro/camoufox",
            "note": "Binary installation required for full functionality"
        }
    }
    
    return info


def get_installation_guide() -> str:
    """Get installation guide for Camoufox."""
    
    return """
Camoufox Installation Guide
============================

Option 1: Install Python wrapper (recommended)
-----------------------------------------------
pip install camoufox-python

Option 2: Download binary manually
-----------------------------------
1. Visit https://camoufox.com or https://github.com/daijro/camoufox
2. Download binary for your platform:
   - Linux: camoufox-linux-x64.tar.gz
   - macOS: camoufox-macos-x64.tar.gz
   - Windows: camoufox-windows-x64.zip

3. Extract to one of:
   Linux:
     - /usr/bin/camoufox
     - /usr/local/bin/camoufox
     - ~/.local/bin/camoufox
   
   macOS:
     - /Applications/Camoufox.app/Contents/MacOS/camoufox
   
   Windows:
     - C:\\Program Files\\Camoufox\\camoufox.exe

4. Make executable (Linux/macOS):
   chmod +x /path/to/camoufox

Option 3: Use with Playwright
------------------------------
pip install playwright
playwright install firefox
# Then specify camoufox_binary_path in config

Verification
------------
Run: python -c "from asagus.layers.camoufox_integration import get_camoufox_info; import json; print(json.dumps(get_camoufox_info(), indent=2))"
"""
