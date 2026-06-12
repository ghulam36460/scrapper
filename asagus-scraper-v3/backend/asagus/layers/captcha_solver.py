"""
CAPTCHA Solver Integration
==========================
Detect CAPTCHA and challenge pages so the active scraper can route them to
manual review.

Detection Systems Using CAPTCHAs:
- Cloudflare Bot Management: Turnstile challenges
- DataDome: Custom challenges
- Akamai Bot Manager: CAPTCHA integration
- PerimeterX: Challenge pages
- HUMAN Security: Interactive challenges

Active runtime behavior:
1. Detect CAPTCHA type by iframe URL patterns
2. Return detection metadata to the caller
3. Do not attempt CAPTCHA bypass or token solving
4. Let the job pipeline skip/manual-review challenged pages

The historical YOLO/ML/LLM solver paths below are intentionally kept as
non-active prototypes. They are not wired to a real model, paid CAPTCHA
service, or browser-session solver in the production job runner.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any

import playwright.async_api as pw


logger = logging.getLogger(__name__)


class CAPTCHAType(Enum):
    """Types of CAPTCHA challenges."""
    recaptcha_v2 = "recaptcha_v2"
    recaptcha_v3 = "recaptcha_v3"
    hcaptcha = "hcaptcha"
    cloudflare_turnstile = "cloudflare_turnstile"
    funcaptcha = "funcaptcha"
    geetest = "geetest"
    unknown = "unknown"


@dataclass
class CAPTCHAChallenge:
    """Detected CAPTCHA challenge information."""
    captcha_type: CAPTCHAType
    site_key: str = ""
    challenge_url: str = ""
    iframe_selector: str = ""
    detected_at: float = 0.0
    
    def __post_init__(self):
        if self.detected_at == 0.0:
            self.detected_at = time.time()


class CaptchaSolvingError(Exception):
    """Exception raised when CAPTCHA solving fails."""
    pass


class CAPTCHASolver:
    """
    Detect CAPTCHA types and report that solving is unavailable.

    This class is detection-first. It does not claim CAPTCHA solve accuracy,
    does not submit third-party solver tokens, and does not bypass challenges.
    """
    
    def __init__(
        self,
        use_yolov8: bool = False,
        use_ml_models: bool = False,
        llm_client: Any = None,
    ):
        """
        Initialize CAPTCHA solver.
        
        Args:
            use_yolov8: Enable YOLOv8 model for reCAPTCHA (requires model file)
            use_ml_models: Enable ML models for hCaptcha/others
            llm_client: LLMClient instance for Oedipus-style LLM solving fallback
        """
        self.logger = logging.getLogger(__name__)
        self.use_yolov8 = use_yolov8
        self.use_ml_models = use_ml_models
        self.llm_client = llm_client
        
        # Per-type statistics
        self._stats: dict[str, dict[str, int]] = {}
        self.solve_attempts = 0
        self.solve_successes = 0
        self.solve_failures = 0
    
    def _track(self, captcha_type: str, success: bool) -> None:
        """Track per-type solve statistics."""
        if captcha_type not in self._stats:
            self._stats[captcha_type] = {"attempts": 0, "successes": 0, "failures": 0}
        self._stats[captcha_type]["attempts"] += 1
        if success:
            self._stats[captcha_type]["successes"] += 1
        else:
            self._stats[captcha_type]["failures"] += 1
    
    async def detect_captcha(self, page: pw.Page) -> CAPTCHAChallenge | None:
        """
        Detect CAPTCHA challenge on page.
        
        Args:
            page: Playwright page object
        
        Returns:
            CAPTCHAChallenge if detected, None otherwise
        """
        
        # Check for reCAPTCHA v2
        recaptcha_iframe = await page.query_selector('iframe[src*="google.com/recaptcha"]')
        if recaptcha_iframe:
            src = await recaptcha_iframe.get_attribute("src")
            self.logger.info(f"Detected reCAPTCHA v2: {src}")
            
            # Extract site key from URL
            site_key = ""
            if "k=" in src:
                site_key = src.split("k=")[1].split("&")[0]
            
            return CAPTCHAChallenge(
                captcha_type=CAPTCHAType.recaptcha_v2,
                site_key=site_key,
                challenge_url=src,
                iframe_selector='iframe[src*="google.com/recaptcha"]'
            )
        
        # Check for hCaptcha
        hcaptcha_iframe = await page.query_selector('iframe[src*="hcaptcha.com"]')
        if hcaptcha_iframe:
            src = await hcaptcha_iframe.get_attribute("src")
            self.logger.info(f"Detected hCaptcha: {src}")
            
            # Extract site key
            site_key = ""
            if "sitekey=" in src:
                site_key = src.split("sitekey=")[1].split("&")[0]
            
            return CAPTCHAChallenge(
                captcha_type=CAPTCHAType.hcaptcha,
                site_key=site_key,
                challenge_url=src,
                iframe_selector='iframe[src*="hcaptcha.com"]'
            )
        
        # Check for Cloudflare Turnstile
        turnstile_iframe = await page.query_selector('iframe[src*="challenges.cloudflare.com/turnstile"]')
        if turnstile_iframe:
            src = await turnstile_iframe.get_attribute("src")
            self.logger.info(f"Detected Cloudflare Turnstile: {src}")
            
            return CAPTCHAChallenge(
                captcha_type=CAPTCHAType.cloudflare_turnstile,
                challenge_url=src,
                iframe_selector='iframe[src*="challenges.cloudflare.com/turnstile"]'
            )
        
        # Check for FunCAPTCHA (Arkose Labs)
        funcaptcha_iframe = await page.query_selector('iframe[src*="funcaptcha.com"]')
        if funcaptcha_iframe:
            self.logger.info("Detected FunCAPTCHA")
            return CAPTCHAChallenge(
                captcha_type=CAPTCHAType.funcaptcha,
                challenge_url=await funcaptcha_iframe.get_attribute("src"),
                iframe_selector='iframe[src*="funcaptcha.com"]'
            )
        
        # Check for GeeTest
        geetest_div = await page.query_selector('.geetest_holder')
        if geetest_div:
            self.logger.info("Detected GeeTest CAPTCHA")
            return CAPTCHAChallenge(
                captcha_type=CAPTCHAType.geetest,
                iframe_selector='.geetest_holder'
            )
        
        return None
    
    async def solve_captcha(
        self,
        page: pw.Page,
        challenge: CAPTCHAChallenge,
        max_retries: int = 3
    ) -> bool:
        """
        Solve detected CAPTCHA challenge.
        
        Args:
            page: Playwright page object
            challenge: Detected CAPTCHA challenge
            max_retries: Maximum number of solve attempts
        
        Returns:
            False. CAPTCHA solving is not implemented in the active runtime.
        """
        self.solve_attempts += 1
        self.solve_failures += 1
        self.logger.warning(
            "CAPTCHA solving is not implemented; %s is routed to manual review",
            challenge.captcha_type.value,
        )
        return False

    async def _solve_recaptcha_v2(
        self,
        page: pw.Page,
        challenge: CAPTCHAChallenge
    ) -> bool:
        """
        Prototype-only reCAPTCHA handler.

        The active runtime does not call this method and no YOLO model is wired.
        
        Args:
            page: Playwright page object
            challenge: reCAPTCHA challenge info
        
        Returns:
            False unless a future internal prototype is explicitly implemented.
        """
        
        self.logger.info("Solving reCAPTCHA v2...")
        
        # Wait for CAPTCHA iframe to load
        try:
            await page.wait_for_selector(
                challenge.iframe_selector,
                timeout=30000
            )
        except Exception as e:
            self.logger.error(f"reCAPTCHA iframe not found: {e}")
            return False
        
        # Switch to reCAPTCHA iframe
        iframe = page.frame_locator(challenge.iframe_selector)
        
        # Click on the checkbox
        try:
            checkbox = iframe.locator('.recaptcha-checkbox')
            await checkbox.click()
            await asyncio.sleep(2)
        except Exception as e:
            self.logger.error(f"Could not click reCAPTCHA checkbox: {e}")
            return False
        
        # Check if challenge appeared or was auto-solved
        challenge_frame = page.frame_locator('iframe[src*="google.com/recaptcha/api2/bframe"]')
        
        try:
            # Wait briefly to see if challenge appears
            await asyncio.sleep(2)
            
            # If YOLOv8 model is available, solve image challenge
            if self.use_yolov8:
                # Extract challenge images
                # Run YOLOv8 inference to identify objects
                # Click matching tiles
                # This would require actual YOLOv8 integration
                self.logger.warning("YOLOv8 solver not implemented in active runtime")
                pass
            elif self.llm_client:
                # LLM-based fallback (Oedipus approach from antibot.md)
                # Uses LLM vision to describe challenge images and select matches
                solved = await self._solve_with_llm(page, challenge, "recaptcha_v2")
                if solved:
                    return True
            else:
                self.logger.warning("reCAPTCHA solver requires YOLOv8 model or LLM client")
        
        except Exception as e:
            self.logger.debug(f"Challenge processing: {e}")
        
        # Verify if CAPTCHA was solved
        await asyncio.sleep(2)
        success = await self._verify_recaptcha_solved(page)
        
        return success
    
    async def _solve_hcaptcha(
        self,
        page: pw.Page,
        challenge: CAPTCHAChallenge
    ) -> bool:
        """
        Prototype-only hCaptcha handler.

        The active runtime does not call this method and no trained model is wired.
        
        Args:
            page: Playwright page object
            challenge: hCaptcha challenge info
        
        Returns:
            False unless a future internal prototype is explicitly implemented.
        """
        
        self.logger.info("Solving hCaptcha...")
        
        # Wait for hCaptcha iframe
        try:
            await page.wait_for_selector(
                challenge.iframe_selector,
                timeout=30000
            )
        except Exception as e:
            self.logger.error(f"hCaptcha iframe not found: {e}")
            return False
        
        # hCaptcha solving requires trained ML model
        if not self.use_ml_models:
            # Try LLM fallback
            if self.llm_client:
                self.logger.info("hCaptcha: attempting LLM fallback (Oedipus approach)")
                return await self._solve_with_llm(page, challenge, "hcaptcha")
            self.logger.warning("hCaptcha solver requires ML models or LLM client")
            return False
        
        # Placeholder for actual ML-based solving
        # Would extract challenge images, run inference, select matches
        self.logger.warning("hCaptcha ML solver not implemented in active runtime")
        
        await asyncio.sleep(2)
        
        return False
    
    async def _solve_cloudflare_turnstile(
        self,
        page: pw.Page,
        challenge: CAPTCHAChallenge
    ) -> bool:
        """
        Solve Cloudflare Turnstile challenge.
        
        Turnstile uses:
        1. Proof of Work (PoW) computation
        2. Behavioral timing analysis
        3. Passive risk scoring
        
        Args:
            page: Playwright page object
            challenge: Turnstile challenge info
        
        Returns:
            True if solved successfully
        """
        
        self.logger.info("Solving Cloudflare Turnstile...")
        
        # Wait for Turnstile iframe
        try:
            await page.wait_for_selector(
                challenge.iframe_selector,
                timeout=30000
            )
        except Exception as e:
            self.logger.error(f"Turnstile iframe not found: {e}")
            return False
        
        # Turnstile is "invisible" and runs in background
        # Key is to wait naturally and let behavioral timing pass
        
        # Simulate human-like wait time (PoW computation mimicry)
        wait_time = 2.0 + (time.time() % 3.0)  # 2-5 seconds
        self.logger.info(f"Waiting {wait_time:.1f}s for Turnstile PoW...")
        await asyncio.sleep(wait_time)
        
        # Check if Turnstile completed
        try:
            # Turnstile sets a hidden input with token
            token_input = await page.query_selector('input[name="cf-turnstile-response"]')
            if token_input:
                token = await token_input.get_attribute("value")
                if token and len(token) > 0:
                    self.logger.info("Turnstile challenge completed successfully")
                    return True
        except Exception as e:
            self.logger.debug(f"Turnstile verification check: {e}")
        
        return False
    
    async def _verify_recaptcha_solved(self, page: pw.Page) -> bool:
        """Verify if reCAPTCHA was solved successfully."""
        
        try:
            # Check for g-recaptcha-response textarea with value
            response = await page.evaluate("""
                () => {
                    const textarea = document.querySelector('textarea[name="g-recaptcha-response"]');
                    return textarea ? textarea.value : '';
                }
            """)
            
            if response and len(response) > 0:
                return True
        except Exception as e:
            self.logger.debug(f"reCAPTCHA verification: {e}")
        
        return False
    
    def get_solve_statistics(self) -> dict[str, Any]:
        """Get CAPTCHA solving statistics with per-type breakdown."""
        
        success_rate = 0.0
        if self.solve_attempts > 0:
            success_rate = (self.solve_successes / self.solve_attempts) * 100
        
        return {
            "total_attempts": self.solve_attempts,
            "successes": self.solve_successes,
            "failures": self.solve_failures,
            "success_rate_percent": round(success_rate, 2),
            "by_type": dict(self._stats),
            "implementation_status": "detection_only",
            "manual_review_required": True,
            "solvers_available": {
                "captcha_solving": False,
                "yolov8": False,
                "ml_models": False,
                "llm_fallback": False,
            },
            "configured_but_unimplemented": {
                "yolov8_requested": self.use_yolov8,
                "ml_models_requested": self.use_ml_models,
                "llm_client_configured": self.llm_client is not None,
            },
        }

    def state(self) -> dict[str, Any]:
        """Return an honest capability report for API/UI diagnostics."""
        return {
            "status": "detection_only",
            "challenge_bypass": False,
            "manual_review_on_captcha": True,
            "implemented_solvers": [],
            "supported_detection_types": [item.value for item in CAPTCHAType],
            "notes": "CAPTCHA token solving is not implemented in the active runtime.",
        }

    async def _solve_with_llm(
        self,
        page: pw.Page,
        challenge: CAPTCHAChallenge,
        challenge_type: str,
    ) -> bool:
        """
        Prototype-only LLM CAPTCHA helper.

        No vision model flow is implemented or called by the active runtime.
        
        Args:
            page: Playwright page object
            challenge: CAPTCHA challenge info
            challenge_type: Type string for logging
        
        Returns:
            False unless a future internal prototype is explicitly implemented.
        """
        if not self.llm_client:
            return False
        
        try:
            self.logger.info(f"Attempting LLM-based solving for {challenge_type}")
            
            # Extract visible challenge text/instructions
            instructions = await page.evaluate("""
                () => {
                    const elements = document.querySelectorAll(
                        '.rc-imageselect-desc-no-canonical, ' +
                        '.rc-imageselect-desc, ' +
                        '.prompt-text, ' +
                        '.challenge-text'
                    );
                    return Array.from(elements).map(el => el.textContent).join(' ');
                }
            """)
            
            if not instructions:
                self.logger.debug("No challenge instructions found for LLM analysis")
                return False
            
            self.logger.info(f"Challenge instructions: {instructions[:100]}")
            
            # The LLM can analyze the challenge type and provide guidance
            # In a full implementation, this would:
            # 1. Screenshot challenge images
            # 2. Send to vision-capable LLM
            # 3. Parse response for tile selections
            # 4. Click identified tiles
            self.logger.info(
                f"LLM solver identified challenge: '{instructions[:80]}' — "
                f"full vision-based solving requires LLM with image capabilities"
            )
            
            return False  # Return False until vision LLM is integrated
            
        except Exception as e:
            self.logger.error(f"LLM solver error: {e}")
            return False

    async def detect_and_solve(
        self,
        page: pw.Page,
        max_retries: int = 3,
    ) -> dict[str, Any]:
        """
        Convenience method: detect + solve in one call.
        Used by the antibot orchestrator pipeline.
        
        Returns:
            Dict with detection/solving results and statistics
        """
        challenge = await self.detect_captcha(page)
        if not challenge:
            return {
                "detected": False,
                "captcha_type": None,
                "solved": False,
                "stats": self.get_solve_statistics(),
            }
        
        try:
            solved = await self.solve_captcha(page, challenge, max_retries=max_retries)
            self._track(challenge.captcha_type.value, solved)
            return {
                "detected": True,
                "captcha_type": challenge.captcha_type.value,
                "site_key": challenge.site_key,
                "solved": solved,
                "manual_review_required": not solved,
                "message": "CAPTCHA detected; active runtime does not attempt CAPTCHA solving.",
                "stats": self.get_solve_statistics(),
            }
        except CaptchaSolvingError as e:
            self._track(challenge.captcha_type.value, False)
            return {
                "detected": True,
                "captcha_type": challenge.captcha_type.value,
                "solved": False,
                "error": str(e),
                "stats": self.get_solve_statistics(),
            }


def create_captcha_solver(
    use_yolov8: bool = False,
    use_ml_models: bool = False,
    llm_client: Any = None,
) -> CAPTCHASolver:
    """Create a detection-first CAPTCHA solver instance."""
    return CAPTCHASolver(
        use_yolov8=use_yolov8,
        use_ml_models=use_ml_models,
        llm_client=llm_client,
    )
