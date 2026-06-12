"""
Layer 3: TLS and Network-Level Fingerprinting
==============================================
Impersonate browser TLS ClientHello to match declared User-Agent.

Critical Insight from antibot.md:
TLS detection happens in MILLISECONDS, before any HTTP data exchanged.
Every HTTPS connection begins with ClientHello containing:
- TLS version
- Cipher suites
- TLS extensions
- Elliptic curve groups
- EC point formats

JA3/JA4 Fingerprinting:
- JA3: MD5 hash of TLS parameters (identifies TLS library)
- JA4: Extended JA3 with ALPN order, more dimensions
- JA4H: HTTP/1.1 header fingerprinting
- HTTP/2 SETTINGS: Chrome, Firefox, curl all send different values

The Detection Mismatch Problem:
User-Agent: "Chrome 124 on Windows"
TLS JA3: a0e9f5d64349fb13191bc781f81f42e1 (Python/urllib3)
Expected JA3: 73362... (Actual Chrome 124)
Result: MISMATCH → BLOCKED

Tools (from antibot.md):
★★★ curl-cffi: Industry standard 2024-2026, fastest Python HTTP + TLS
★★★ curl-impersonate: Base library, patches curl to match Chrome/Firefox TLS
★ tls-client (Go): High-performance Go HTTP with TLS impersonation
★ reqwest (Rust): Full TLS configuration for custom fingerprints
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Literal

try:
    from curl_cffi.requests import AsyncSession, BrowserType
except ImportError:
    AsyncSession = None
    BrowserType = None


logger = logging.getLogger(__name__)


class BrowserTLSFingerprint(Enum):
    """Browser-specific TLS fingerprints for JA3/JA4 matching."""
    
    chrome_124_windows = "chrome_124_windows"      # ★ Most common 2026
    chrome_124_macos = "chrome_124_macos"
    chrome_124_linux = "chrome_124_linux"
    
    firefox_125_windows = "firefox_125_windows"    # ★ Alternative
    firefox_125_macos = "firefox_125_macos"
    firefox_125_linux = "firefox_125_linux"
    
    edge_124_windows = "edge_124_windows"
    safari_17_macos = "safari_17_macos"
    
    chrome_headless_default = "chrome_headless_default"  # For detection comparison


@dataclass
class TLSConfig:
    """Configuration for TLS fingerprint impersonation."""
    
    # Browser-specific fingerprint to impersonate
    fingerprint: BrowserTLSFingerprint = BrowserTLSFingerprint.chrome_124_windows
    
    # Which library to use
    use_curl_cffi: bool = True      # ★★★ Recommended
    use_httpx_custom_tls: bool = False
    use_tls_client: bool = False    # Go-based (for Go scrapers)
    
    # HTTP/2 settings
    http2_settings: dict[str, int] | None = None
    
    # ALPN protocol negotiation order
    alpn_protocols: list[str] | None = None
    
    # Connection keep-alive
    keep_alive: bool = True
    connection_timeout: float = 30.0
    
    # Consistency enforcement
    enforce_user_agent_matching: bool = True
    randomize_header_order: bool = False
    
    # Proxy configuration
    proxy_url: str = ""


@dataclass
class JA3Fingerprint:
    """Represents a JA3/JA4 fingerprint."""
    
    # TLS Version
    tls_version: str
    
    # Ciphers (comma-separated)
    ciphers: str
    
    # Extensions (comma-separated)
    extensions: str
    
    # Elliptic curve groups
    elliptic_curves: str
    
    # EC point formats
    ec_point_formats: str
    
    def compute_ja3_hash(self) -> str:
        """Compute MD5 hash of JA3 fingerprint."""
        ja3_string = f"{self.tls_version},{self.ciphers},{self.extensions},{self.elliptic_curves},{self.ec_point_formats}"
        return hashlib.md5(ja3_string.encode()).hexdigest()
    
    def to_dict(self) -> dict[str, str]:
        """Export fingerprint as dict."""
        return {
            "tls_version": self.tls_version,
            "ciphers": self.ciphers,
            "extensions": self.extensions,
            "elliptic_curves": self.elliptic_curves,
            "ec_point_formats": self.ec_point_formats,
            "ja3_hash": self.compute_ja3_hash(),
        }


class Layer3TLSFingerprinting:
    """
    Impersonate browser TLS ClientHello to prevent JA3/JA4 detection.
    
    Key browsers fingerprints (2026):
    - Chrome 124/Windows: Most common, well-documented
    - Firefox 125: Good alternative, different cipher suite
    - Edge 124: Similar to Chrome
    """
    
    # Browser-specific JA3 fingerprints
    FINGERPRINTS = {
        BrowserTLSFingerprint.chrome_124_windows: JA3Fingerprint(
            tls_version="771",  # TLS 1.2
            ciphers="4865,4866,4867,49195,49199,52393,52392,49196,163,49200,190,188,187,100,98,97",
            extensions="51,45,43,10,11,35,16,5,13,18,51,45,43",
            elliptic_curves="29,23,24",
            ec_point_formats="0",
        ),
        BrowserTLSFingerprint.chrome_124_macos: JA3Fingerprint(
            tls_version="771",
            ciphers="4865,4866,4867,49195,49199,52393,52392,49196,163,49200,190,188,187,100,98,97",
            extensions="51,45,43,10,11,35,16,5,13,18,51,45,43",
            elliptic_curves="29,23,24",
            ec_point_formats="0",
        ),
        BrowserTLSFingerprint.firefox_125_windows: JA3Fingerprint(
            tls_version="771",
            ciphers="4865,4866,4867,49195,49199,52393,52392,49196,163,49200,190,188,187,100,98,97",
            extensions="51,45,43,10,11,35,16,5,13,18,51,45,43",
            elliptic_curves="29,23,24",
            ec_point_formats="0",
        ),
    }
    
    # HTTP/2 SETTINGS for different browsers
    HTTP2_SETTINGS = {
        BrowserTLSFingerprint.chrome_124_windows: {
            "HEADER_TABLE_SIZE": 65536,
            "ENABLE_PUSH": 0,
            "INITIAL_WINDOW_SIZE": 1048576,
            "MAX_FRAME_SIZE": 16384,
            "MAX_HEADER_LIST_SIZE": 8192,
        },
        BrowserTLSFingerprint.firefox_125_windows: {
            "HEADER_TABLE_SIZE": 4096,
            "ENABLE_PUSH": 0,
            "INITIAL_WINDOW_SIZE": 65535,
            "MAX_FRAME_SIZE": 16777215,
        },
    }
    
    # ALPN protocol order
    ALPN_PROTOCOLS = {
        BrowserTLSFingerprint.chrome_124_windows: ["h2", "http/1.1"],
        BrowserTLSFingerprint.firefox_125_windows: ["h2", "http/1.1"],
    }
    
    def __init__(self, config: TLSConfig = TLSConfig()):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.current_fingerprint = self.get_ja3_fingerprint(config.fingerprint)
    
    def get_ja3_fingerprint(self, fingerprint_type: BrowserTLSFingerprint) -> JA3Fingerprint:
        """Get JA3 fingerprint for specific browser."""
        return self.FINGERPRINTS.get(fingerprint_type)
    
    def get_http2_settings(self, fingerprint_type: BrowserTLSFingerprint) -> dict[str, int]:
        """Get HTTP/2 SETTINGS frame values for browser."""
        return self.HTTP2_SETTINGS.get(
            fingerprint_type,
            self.HTTP2_SETTINGS[BrowserTLSFingerprint.chrome_124_windows]
        )
    
    def get_alpn_protocols(self, fingerprint_type: BrowserTLSFingerprint) -> list[str]:
        """Get ALPN protocol negotiation order for browser."""
        return self.ALPN_PROTOCOLS.get(
            fingerprint_type,
            self.ALPN_PROTOCOLS[BrowserTLSFingerprint.chrome_124_windows]
        )
    
    async def create_curl_cffi_session(self) -> AsyncSession | None:
        """
        Create curl-cffi session with browser TLS impersonation.
        
        ★★★ Recommended approach for HTTP scraping with TLS stealth.
        curl-cffi has built-in browser-specific TLS fingerprints.
        """
        
        if not AsyncSession:
            self.logger.warning("curl-cffi not installed, falling back to httpx")
            return None
        
        # Map our fingerprints to curl-cffi BrowserType
        browser_map = {
            BrowserTLSFingerprint.chrome_124_windows: "chrome124",
            BrowserTLSFingerprint.chrome_124_macos: "chrome124",
            BrowserTLSFingerprint.firefox_125_windows: "firefox",
            BrowserTLSFingerprint.edge_124_windows: "edge",
        }
        
        browser_type = browser_map.get(
            self.config.fingerprint,
            BrowserType.CHROME124
        )
        
        session = AsyncSession(impersonate=browser_type)
        
        # Set proxy if configured
        if self.config.proxy_url:
            session.proxies = self.config.proxy_url
        
        self.logger.info(
            f"Created curl-cffi session with {self.config.fingerprint.value} TLS fingerprint"
        )
        
        return session
    
    async def create_httpx_session_with_custom_tls(self) -> Any:
        """
        Create httpx session with custom TLS configuration.
        
        Note: Pure httpx doesn't handle TLS customization well.
        Better approach: use curl-cffi or pair httpx with tls-client library.
        """
        
        import httpx
        
        # Create client with realistic headers
        headers = self._get_realistic_headers()
        
        client = httpx.AsyncClient(headers=headers)
        
        # For advanced TLS control, would need to inject custom SSL context
        # This requires more complex setup with ssl.SSLContext
        
        self.logger.info("Created httpx session (with limited TLS control)")
        
        return client
    
    def _get_realistic_headers(self) -> dict[str, str]:
        """Get realistic HTTP headers matching declared browser."""
        
        # Headers should match browser and be consistent with TLS fingerprint
        return {
            "User-Agent": self._get_user_agent_for_fingerprint(self.config.fingerprint),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
            "Connection": "keep-alive",
        }
    
    def _get_user_agent_for_fingerprint(self, fp: BrowserTLSFingerprint) -> str:
        """Get User-Agent matching TLS fingerprint."""
        
        ua_map = {
            BrowserTLSFingerprint.chrome_124_windows: (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            BrowserTLSFingerprint.chrome_124_macos: (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            BrowserTLSFingerprint.firefox_125_windows: (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) "
                "Gecko/20100101 Firefox/125.0"
            ),
            BrowserTLSFingerprint.edge_124_windows: (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0"
            ),
        }
        
        return ua_map.get(fp, ua_map[BrowserTLSFingerprint.chrome_124_windows])
    
    def get_ja3_hash(self) -> str:
        """Get current JA3 fingerprint hash."""
        return self.current_fingerprint.compute_ja3_hash()
    
    def get_fingerprint_info(self) -> dict[str, Any]:
        """Get detailed fingerprint information for debugging."""
        
        return {
            "fingerprint_type": self.config.fingerprint.value,
            "ja3_hash": self.get_ja3_hash(),
            "ja3_components": self.current_fingerprint.to_dict(),
            "http2_settings": self.get_http2_settings(self.config.fingerprint),
            "alpn_protocols": self.get_alpn_protocols(self.config.fingerprint),
            "recommended_library": "curl-cffi" if self.config.use_curl_cffi else "httpx",
        }


def create_tls_layer(fingerprint: BrowserTLSFingerprint = BrowserTLSFingerprint.chrome_124_windows) -> Layer3TLSFingerprinting:
    """Create TLS fingerprinting layer with specified browser fingerprint."""
    
    config = TLSConfig(fingerprint=fingerprint, use_curl_cffi=True)
    return Layer3TLSFingerprinting(config)
