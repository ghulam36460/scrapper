"""
Adaptive Mode Switching Based on Detection
===========================================
Automatically adapt evasion strategies when detection occurs.

From Requirements 16:
- Switch strategies when HTTP 403, 429, or CAPTCHA detected
- Rotate stealth approach after 3 detections
- Rotate device profile after 5 detections
- Rotate proxy IP after 7 detections
- Implement exponential backoff (1s → 60s max)
- Reset counter after 100 successful requests
- Track detection statistics per domain

Key Insight from antibot.md:
"If an approach has failed twice, diagnose the root cause rather than
making incremental patches. Try a fundamentally different approach."

Adaptive Strategy Hierarchy:
1. Light touch: Exponential backoff + retry
2. Medium touch: Rotate proxy IP
3. Heavy touch: Rotate device profile
4. Nuclear option: Change stealth approach entirely
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from asagus.layers.antibot_layer2_stealth import StealthApproach
from asagus.layers.antibot_layer4_fingerprinting import DeviceProfile, REALISTIC_DEVICE_PROFILES


logger = logging.getLogger(__name__)


class AdaptiveAction(Enum):
    """Types of adaptive actions."""
    none = "none"
    exponential_backoff = "exponential_backoff"
    rotate_proxy = "rotate_proxy"
    rotate_device_profile = "rotate_device_profile"
    change_stealth_approach = "change_stealth_approach"
    solve_captcha = "solve_captcha"
    full_reset = "full_reset"


@dataclass
class DetectionCounter:
    """Track detections for a specific domain/target."""
    domain: str
    detection_count: int = 0
    successful_requests: int = 0
    last_detection_time: float = 0.0
    current_backoff_seconds: float = 1.0
    consecutive_successes: int = 0
    
    # Actions taken
    proxy_rotations: int = 0
    profile_rotations: int = 0
    stealth_changes: int = 0
    
    def increment_detection(self) -> None:
        """Increment detection counter."""
        self.detection_count += 1
        self.consecutive_successes = 0
        self.last_detection_time = time.time()
    
    def increment_success(self) -> None:
        """Increment successful request counter."""
        self.successful_requests += 1
        self.consecutive_successes += 1
        
        # Reset detection counter after 100 successful requests
        if self.consecutive_successes >= 100:
            self.detection_count = 0
            self.consecutive_successes = 0
            self.current_backoff_seconds = 1.0
    
    def calculate_backoff(self) -> float:
        """Calculate exponential backoff delay."""
        # Exponential backoff: 1s, 2s, 4s, 8s, 16s, 32s, 60s (max)
        backoff = min(self.current_backoff_seconds, 60.0)
        self.current_backoff_seconds = min(backoff * 2, 60.0)
        return backoff


@dataclass
class AdaptiveConfig:
    """Configuration for adaptive mode switching."""
    
    # Detection thresholds
    threshold_light: int = 3     # Rotate proxy
    threshold_medium: int = 5    # Rotate device profile
    threshold_heavy: int = 7     # Change stealth approach
    
    # Backoff settings
    initial_backoff_seconds: float = 1.0
    max_backoff_seconds: float = 60.0
    
    # Success reset threshold
    success_reset_threshold: int = 100
    
    # Available options for rotation
    available_stealth_approaches: list[StealthApproach] = field(default_factory=lambda: [
        StealthApproach.javascript_shim,
        StealthApproach.patchright,
        StealthApproach.camoufox,
    ])
    
    available_device_profiles: list[str] = field(default_factory=lambda: [
        "windows_chrome",
        "macos_chrome",
        "linux_firefox",
    ])


class AdaptiveModeController:
    """
    Control adaptive mode switching based on detection events.
    
    Implements intelligent strategy adjustment when bot detection occurs:
    - Light detections (1-3): Exponential backoff + retry
    - Medium detections (4-5): Rotate proxy IP
    - Heavy detections (6-7): Rotate device profile
    - Critical detections (8+): Change stealth approach
    
    Automatically resets counters after successful runs.
    """
    
    def __init__(self, config: AdaptiveConfig = AdaptiveConfig()):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Track detections per domain
        self.detection_counters: dict[str, DetectionCounter] = {}
        
        # Current configuration indices
        self.current_stealth_index = 0
        self.current_profile_index = 0
    
    def get_or_create_counter(self, domain: str) -> DetectionCounter:
        """Get or create detection counter for domain."""
        
        if domain not in self.detection_counters:
            self.detection_counters[domain] = DetectionCounter(domain=domain)
        
        return self.detection_counters[domain]
    
    async def handle_detection(
        self,
        domain: str,
        status_code: int,
        captcha_detected: bool = False
    ) -> AdaptiveAction:
        """
        Handle detection event and determine adaptive action.
        
        Args:
            domain: Target domain
            status_code: HTTP status code (403, 429, etc.)
            captcha_detected: Whether CAPTCHA was detected
        
        Returns:
            Recommended adaptive action
        """
        
        counter = self.get_or_create_counter(domain)
        counter.increment_detection()
        
        self.logger.warning(
            f"Detection #{counter.detection_count} on {domain} "
            f"(HTTP {status_code}, CAPTCHA: {captcha_detected})"
        )
        
        # Determine action based on detection count
        if captcha_detected:
            self.logger.info("→ Action: Solve CAPTCHA")
            return AdaptiveAction.solve_captcha
        
        elif status_code == 429:
            # Rate limit - always backoff
            backoff = counter.calculate_backoff()
            self.logger.info(f"→ Action: Rate limit backoff ({backoff:.1f}s)")
            await asyncio.sleep(backoff)
            return AdaptiveAction.exponential_backoff
        
        elif counter.detection_count >= self.config.threshold_heavy:
            # Heavy detections - change stealth approach
            self.logger.warning(
                f"→ Action: Change stealth approach (threshold {self.config.threshold_heavy})"
            )
            counter.stealth_changes += 1
            return AdaptiveAction.change_stealth_approach
        
        elif counter.detection_count >= self.config.threshold_medium:
            # Medium detections - rotate device profile
            self.logger.warning(
                f"→ Action: Rotate device profile (threshold {self.config.threshold_medium})"
            )
            counter.profile_rotations += 1
            return AdaptiveAction.rotate_device_profile
        
        elif counter.detection_count >= self.config.threshold_light:
            # Light detections - rotate proxy
            self.logger.info(
                f"→ Action: Rotate proxy (threshold {self.config.threshold_light})"
            )
            counter.proxy_rotations += 1
            return AdaptiveAction.rotate_proxy
        
        else:
            # First few detections - just backoff
            backoff = counter.calculate_backoff()
            self.logger.info(f"→ Action: Exponential backoff ({backoff:.1f}s)")
            await asyncio.sleep(backoff)
            return AdaptiveAction.exponential_backoff
    
    async def handle_success(self, domain: str) -> None:
        """
        Handle successful request.
        
        Args:
            domain: Target domain
        """
        
        counter = self.get_or_create_counter(domain)
        counter.increment_success()
        
        # Log if counter was reset
        if counter.consecutive_successes == 1 and counter.detection_count == 0:
            self.logger.info(
                f"✓ Detection counter reset for {domain} after 100 successful requests"
            )
    
    def get_next_stealth_approach(self) -> StealthApproach:
        """
        Get next stealth approach for rotation.
        
        Returns:
            Next stealth approach from available options
        """
        
        approaches = self.config.available_stealth_approaches
        
        if not approaches:
            return StealthApproach.javascript_shim
        
        self.current_stealth_index = (self.current_stealth_index + 1) % len(approaches)
        approach = approaches[self.current_stealth_index]
        
        self.logger.info(f"Rotated to stealth approach: {approach.value}")
        return approach
    
    def get_next_device_profile(self) -> DeviceProfile:
        """
        Get next device profile for rotation.
        
        Returns:
            Next device profile from available options
        """
        
        profiles = self.config.available_device_profiles
        
        if not profiles:
            return DeviceProfile()
        
        self.current_profile_index = (self.current_profile_index + 1) % len(profiles)
        profile_name = profiles[self.current_profile_index]
        
        profile = REALISTIC_DEVICE_PROFILES.get(profile_name, DeviceProfile())
        
        self.logger.info(f"Rotated to device profile: {profile_name}")
        return profile
    
    def get_statistics(self) -> dict[str, Any]:
        """Get adaptive mode statistics."""
        
        stats = {
            "domains_tracked": len(self.detection_counters),
            "per_domain": {}
        }
        
        for domain, counter in self.detection_counters.items():
            stats["per_domain"][domain] = {
                "detection_count": counter.detection_count,
                "successful_requests": counter.successful_requests,
                "consecutive_successes": counter.consecutive_successes,
                "proxy_rotations": counter.proxy_rotations,
                "profile_rotations": counter.profile_rotations,
                "stealth_changes": counter.stealth_changes,
                "current_backoff_seconds": counter.current_backoff_seconds,
                "detection_rate_percent": (
                    (counter.detection_count / max(counter.successful_requests, 1)) * 100
                    if counter.successful_requests > 0 else 0.0
                ),
            }
        
        return stats
    
    def reset_domain(self, domain: str) -> None:
        """Reset detection counter for specific domain."""
        
        if domain in self.detection_counters:
            del self.detection_counters[domain]
            self.logger.info(f"Reset detection counter for {domain}")
    
    def reset_all(self) -> None:
        """Reset all detection counters."""
        
        self.detection_counters.clear()
        self.logger.info("Reset all detection counters")


def create_adaptive_controller(config: AdaptiveConfig = AdaptiveConfig()) -> AdaptiveModeController:
    """Create adaptive mode controller instance."""
    return AdaptiveModeController(config)
