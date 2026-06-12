"""
Detection System Coverage
==========================
Handle all major commercial bot detection platforms.

From antibot.md research - Detection Systems (2026):
1. Cloudflare Turnstile / Bot Management - Turnstile (PoW + behavior)
2. DataDome - ML behavioral analysis
3. Akamai Bot Manager - JA4+ TLS + HTTP/2 fingerprinting
4. PerimeterX / HUMAN Security - Behavioral biometrics
5. Imperva Advanced Bot Protection - Device profile consistency
6. Distil Networks (Imperva) - TLS + behavioral
7. Shape Security - Advanced ML

All detection systems check across ALL 5 layers simultaneously:
- Layer 1: Automation framework signature
- Layer 2: JS environment integrity
- Layer 3: TLS/network fingerprinting (JA3/JA4)
- Layer 4: Browser/DOM fingerprinting
- Layer 5: Behavioral biometrics

Key Insight: A single failure in ANY layer = BLOCKED
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import playwright.async_api as pw


logger = logging.getLogger(__name__)


class DetectionSystem(Enum):
    """Commercial bot detection platforms."""
    cloudflare = "cloudflare"
    datadome = "datadome"
    akamai = "akamai"
    perimeterx = "perimeterx"
    human_security = "human_security"
    imperva = "imperva"
    distil_networks = "distil_networks"
    shape_security = "shape_security"
    recaptcha_enterprise = "recaptcha_enterprise"
    unknown = "unknown"


class ChallengeType(Enum):
    """Types of challenges from detection systems."""
    captcha = "captcha"
    turnstile = "turnstile"
    javascript_challenge = "javascript_challenge"
    rate_limit = "rate_limit"
    ip_block = "ip_block"
    behavioral_analysis = "behavioral_analysis"
    fingerprint_mismatch = "fingerprint_mismatch"
    http_403 = "http_403"
    http_429 = "http_429"
    none_detected = "none_detected"


@dataclass
class DetectionEvent:
    """Record of a detection event."""
    timestamp: float = field(default_factory=time.time)
    detection_system: DetectionSystem = DetectionSystem.unknown
    challenge_type: ChallengeType = ChallengeType.none_detected
    url: str = ""
    status_code: int = 0
    resolution_attempted: bool = False
    resolution_successful: bool = False
    resolution_time_seconds: float = 0.0
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class DetectionStatistics:
    """Statistics per target domain."""
    domain: str
    total_requests: int = 0
    detection_count: int = 0
    successful_resolutions: int = 0
    failed_resolutions: int = 0
    avg_resolution_time: float = 0.0
    most_common_challenge: ChallengeType = ChallengeType.none_detected
    detection_rate_percent: float = 0.0
    
    def update(self, event: DetectionEvent) -> None:
        """Update statistics with new detection event."""
        self.total_requests += 1
        
        if event.challenge_type != ChallengeType.none_detected:
            self.detection_count += 1
        
        if event.resolution_attempted:
            if event.resolution_successful:
                self.successful_resolutions += 1
            else:
                self.failed_resolutions += 1
        
        # Update detection rate
        if self.total_requests > 0:
            self.detection_rate_percent = (self.detection_count / self.total_requests) * 100


class DetectionSystemHandler:
    """
    Handle all major commercial bot detection platforms.
    
    Provides:
    - Detection system identification
    - Challenge type detection
    - Event logging and statistics
    - Fallback strategy recommendations
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.detection_events: list[DetectionEvent] = []
        self.domain_stats: dict[str, DetectionStatistics] = {}
    
    async def detect_protection_system(self, page: pw.Page) -> DetectionSystem:
        """
        Detect which bot protection system is in use.
        
        Args:
            page: Playwright page object
        
        Returns:
            Detected protection system
        """
        
        # Check for Cloudflare
        if await self._is_cloudflare(page):
            self.logger.info("Detected Cloudflare Bot Management")
            return DetectionSystem.cloudflare
        
        # Check for DataDome
        if await self._is_datadome(page):
            self.logger.info("Detected DataDome")
            return DetectionSystem.datadome
        
        # Check for Akamai
        if await self._is_akamai(page):
            self.logger.info("Detected Akamai Bot Manager")
            return DetectionSystem.akamai
        
        # Check for PerimeterX / HUMAN Security
        if await self._is_perimeterx(page):
            self.logger.info("Detected PerimeterX/HUMAN Security")
            return DetectionSystem.perimeterx
        
        # Check for Imperva
        if await self._is_imperva(page):
            self.logger.info("Detected Imperva Advanced Bot Protection")
            return DetectionSystem.imperva
        
        # Check for Shape Security
        if await self._is_shape(page):
            self.logger.info("Detected Shape Security")
            return DetectionSystem.shape_security
        
        return DetectionSystem.unknown
    
    async def detect_challenge_type(
        self,
        page: pw.Page,
        response: pw.Response | None = None
    ) -> ChallengeType:
        """
        Detect the type of challenge presented.
        
        Args:
            page: Playwright page object
            response: HTTP response (optional)
        
        Returns:
            Type of challenge detected
        """
        
        # Check HTTP status codes first
        if response:
            if response.status == 403:
                self.logger.warning("HTTP 403 - Access forbidden")
                return ChallengeType.http_403
            elif response.status == 429:
                self.logger.warning("HTTP 429 - Rate limit exceeded")
                return ChallengeType.rate_limit
        
        # Check for CAPTCHAs
        captcha_selectors = [
            'iframe[src*="recaptcha"]',
            'iframe[src*="hcaptcha"]',
            'iframe[src*="funcaptcha"]',
            '.g-recaptcha',
            '#h-captcha',
        ]
        
        for selector in captcha_selectors:
            if await page.query_selector(selector):
                self.logger.info(f"CAPTCHA detected: {selector}")
                return ChallengeType.captcha
        
        # Check for Cloudflare Turnstile
        if await page.query_selector('iframe[src*="challenges.cloudflare.com/turnstile"]'):
            self.logger.info("Cloudflare Turnstile challenge detected")
            return ChallengeType.turnstile
        
        # Check for JavaScript challenge
        page_content = await page.content()
        if "challenge-running" in page_content or "Just a moment" in page_content:
            self.logger.info("JavaScript challenge detected")
            return ChallengeType.javascript_challenge
        
        return ChallengeType.none_detected
    
    async def _is_cloudflare(self, page: pw.Page) -> bool:
        """Check if Cloudflare protection is active."""
        
        try:
            # Check for Cloudflare cookies
            cookies = await page.context.cookies()
            for cookie in cookies:
                if cookie['name'].startswith('cf_') or cookie['name'] == '__cflb':
                    return True
            
            # Check for Cloudflare challenge page
            content = await page.content()
            if "Cloudflare" in content and ("Just a moment" in content or "challenge-running" in content):
                return True
            
            # Check for Turnstile
            if await page.query_selector('iframe[src*="challenges.cloudflare.com"]'):
                return True
        
        except Exception as e:
            self.logger.debug(f"Cloudflare detection error: {e}")
        
        return False
    
    async def _is_datadome(self, page: pw.Page) -> bool:
        """Check if DataDome protection is active."""
        
        try:
            # Check for DataDome cookies
            cookies = await page.context.cookies()
            for cookie in cookies:
                if cookie['name'].startswith('datadome'):
                    return True
            
            # Check for DataDome scripts
            content = await page.content()
            if "datadome" in content.lower():
                return True
            
            # Check for DataDome challenge
            if await page.query_selector('.datadome-captcha'):
                return True
        
        except Exception as e:
            self.logger.debug(f"DataDome detection error: {e}")
        
        return False
    
    async def _is_akamai(self, page: pw.Page) -> bool:
        """Check if Akamai Bot Manager is active."""
        
        try:
            # Check for Akamai cookies
            cookies = await page.context.cookies()
            for cookie in cookies:
                if 'akamai' in cookie['name'].lower() or cookie['name'].startswith('_abck'):
                    return True
            
            # Check for Akamai sensor data
            has_sensor = await page.evaluate("""
                () => window._abck !== undefined || window.akam !== undefined
            """)
            if has_sensor:
                return True
        
        except Exception as e:
            self.logger.debug(f"Akamai detection error: {e}")
        
        return False
    
    async def _is_perimeterx(self, page: pw.Page) -> bool:
        """Check if PerimeterX/HUMAN Security is active."""
        
        try:
            # Check for PerimeterX cookies
            cookies = await page.context.cookies()
            for cookie in cookies:
                if cookie['name'].startswith('_px') or cookie['name'].startswith('_pxhd'):
                    return True
            
            # Check for PerimeterX scripts
            content = await page.content()
            if "perimeterx" in content.lower() or "_pxAppId" in content:
                return True
            
            # Check for PerimeterX challenge
            if await page.query_selector('#px-captcha'):
                return True
        
        except Exception as e:
            self.logger.debug(f"PerimeterX detection error: {e}")
        
        return False
    
    async def _is_imperva(self, page: pw.Page) -> bool:
        """Check if Imperva Advanced Bot Protection is active."""
        
        try:
            # Check for Imperva/Incapsula cookies
            cookies = await page.context.cookies()
            for cookie in cookies:
                if 'incap_' in cookie['name'] or 'visid_incap' in cookie['name']:
                    return True
            
            # Check for Imperva challenge
            content = await page.content()
            if "Incapsula" in content or "_Incapsula_Resource" in content:
                return True
        
        except Exception as e:
            self.logger.debug(f"Imperva detection error: {e}")
        
        return False
    
    async def _is_shape(self, page: pw.Page) -> bool:
        """Check if Shape Security is active."""
        
        try:
            # Check for Shape cookies
            cookies = await page.context.cookies()
            for cookie in cookies:
                if 'shape' in cookie['name'].lower():
                    return True
            
            # Check for Shape scripts
            content = await page.content()
            if "shapesecurity" in content.lower():
                return True
        
        except Exception as e:
            self.logger.debug(f"Shape detection error: {e}")
        
        return False
    
    def log_detection_event(
        self,
        event: DetectionEvent
    ) -> None:
        """
        Log a detection event and update statistics.
        
        Args:
            event: Detection event to log
        """
        
        self.detection_events.append(event)
        
        # Extract domain from URL
        try:
            from urllib.parse import urlparse
            domain = urlparse(event.url).netloc
        except Exception:
            domain = "unknown"
        
        # Update domain statistics
        if domain not in self.domain_stats:
            self.domain_stats[domain] = DetectionStatistics(domain=domain)
        
        self.domain_stats[domain].update(event)
        
        # Log event
        self.logger.info(
            f"Detection Event: {event.detection_system.value} | "
            f"{event.challenge_type.value} | "
            f"Status: {event.status_code} | "
            f"Resolved: {event.resolution_successful}"
        )
    
    def get_statistics_for_domain(self, domain: str) -> DetectionStatistics | None:
        """Get detection statistics for specific domain."""
        return self.domain_stats.get(domain)
    
    def get_all_statistics(self) -> dict[str, DetectionStatistics]:
        """Get detection statistics for all domains."""
        return self.domain_stats.copy()
    
    def get_fallback_strategy(
        self,
        detection_system: DetectionSystem,
        challenge_type: ChallengeType
    ) -> dict[str, Any]:
        """
        Get recommended fallback strategy for detected challenge.
        
        Args:
            detection_system: Detected protection system
            challenge_type: Type of challenge
        
        Returns:
            Dictionary with recommended actions
        """
        
        strategy = {
            "rotate_proxy": False,
            "rotate_device_profile": False,
            "change_stealth_approach": False,
            "solve_captcha": False,
            "wait_and_retry": False,
            "wait_seconds": 0,
            "notes": "",
        }
        
        # Cloudflare strategies
        if detection_system == DetectionSystem.cloudflare:
            if challenge_type == ChallengeType.turnstile:
                strategy["solve_captcha"] = True
                strategy["wait_seconds"] = 3
                strategy["notes"] = "Solve Turnstile with PoW simulation"
            elif challenge_type == ChallengeType.rate_limit:
                strategy["wait_and_retry"] = True
                strategy["wait_seconds"] = 60
                strategy["rotate_proxy"] = True
                strategy["notes"] = "Rate limited - wait and rotate IP"
        
        # DataDome strategies
        elif detection_system == DetectionSystem.datadome:
            strategy["rotate_device_profile"] = True
            strategy["change_stealth_approach"] = True
            strategy["notes"] = "DataDome ML detected inconsistency - rotate profile"
        
        # Akamai strategies
        elif detection_system == DetectionSystem.akamai:
            strategy["change_stealth_approach"] = True
            strategy["rotate_proxy"] = True
            strategy["notes"] = "Akamai JA4+ detected TLS mismatch - enhance TLS fingerprint"
        
        # PerimeterX strategies
        elif detection_system == DetectionSystem.perimeterx:
            strategy["rotate_device_profile"] = True
            strategy["wait_seconds"] = 5
            strategy["notes"] = "PerimeterX behavioral analysis - enhance Layer 5"
        
        # Imperva strategies
        elif detection_system == DetectionSystem.imperva:
            strategy["rotate_proxy"] = True
            strategy["rotate_device_profile"] = True
            strategy["notes"] = "Imperva device clustering detected - fresh profile needed"
        
        # Generic 403/429 strategies
        elif challenge_type == ChallengeType.http_403:
            strategy["rotate_proxy"] = True
            strategy["rotate_device_profile"] = True
            strategy["notes"] = "IP or device blocked - full rotation"
        
        elif challenge_type == ChallengeType.rate_limit:
            strategy["wait_and_retry"] = True
            strategy["wait_seconds"] = 30
            strategy["rotate_proxy"] = True
            strategy["notes"] = "Rate limit - exponential backoff"
        
        return strategy


def create_detection_handler() -> DetectionSystemHandler:
    """Create detection system handler instance."""
    return DetectionSystemHandler()
