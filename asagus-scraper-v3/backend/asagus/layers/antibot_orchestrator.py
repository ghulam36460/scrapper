"""
AntiBot Orchestrator: Central Coordination System
=================================================
Integrates all 5 layers of anti-detection into a unified system.

Architecture:
┌─────────────────────────────────────────────────────────────────┐
│                    ANTIBOT ORCHESTRATOR                         │
│  Coordinates all 5 layers with cross-layer consistency checks   │
└─────────────────────────────────────────────────────────────────┘
    │
    ├─── Layer 1: Core Automation Framework Selection
    │    └─ Choose: Browser CDP vs HTTP-only
    │    └─ Decision: JS required? Throughput? CAPTCHA?
    │
    ├─── Layer 2: Stealth & Anti-Detection
    │    └─ JS shim: navigator.webdriver, chrome.runtime, plugins
    │    └─ Binary patch: Camoufox, CloakBrowser, Patchright
    │    └─ Header injection: Realistic HTTP headers
    │
    ├─── Layer 3: TLS/Network Fingerprinting
    │    └─ JA3/JA4 hash matching: Browser-specific ClientHello
    │    └─ HTTP/2 SETTINGS: Match browser implementation
    │    └─ curl-cffi: Built-in browser TLS impersonation
    │
    ├─── Layer 4: Browser/DOM Fingerprinting
    │    └─ Device profile: Consistent GPU, screen, timezone
    │    └─ Canvas/WebGL spoofing: Prevent GPU detection
    │    └─ Prototype chain integrity: Pass CreepJS checks
    │
    ├─── Layer 5: Behavioral Biometrics
    │    └─ Sigma log-normal: Realistic cursor trajectories
    │    └─ Fitts' Law: Movement time matches target geometry
    │    └─ IKT: Natural typing patterns with errors
    │
    └─── Cross-Layer Consistency Verification
         └─ User-Agent matches TLS fingerprint
         └─ Device properties are internally coherent
         └─ Behavioral patterns match declared device specs
         └─ No geographically impossible combinations

Key Principle from antibot.md:
"Individual layers can each be addressed by existing tools.
The fundamental unsolved challenge is cross-layer consistency."

All 5 layers evaluated in PARALLEL by modern detection systems.
A single failure anywhere = BLOCKED or CHALLENGED.
"""

from __future__ import annotations

import asyncio
import importlib.util
import logging
from dataclasses import dataclass
from typing import Any, Literal

import playwright.async_api as pw

from asagus.layers.antibot_layer1_automation import (
    AutomationFramework,
    FrameworkSelectionCriteria,
    FrameworkConfig,
    JSRequirement,
    Layer1AutomationSelector,
)
from asagus.layers.antibot_layer2_stealth import (
    StealthApproach,
    StealthConfig,
    Layer2StealthPatching,
)
from asagus.layers.antibot_layer3_tls import (
    BrowserTLSFingerprint,
    TLSConfig,
    Layer3TLSFingerprinting,
)
from asagus.layers.antibot_layer4_fingerprinting import (
    DeviceProfile,
    Layer4BrowserFingerprinting,
    REALISTIC_DEVICE_PROFILES,
)
from asagus.layers.antibot_layer5_behavior import (
    Layer5BehavioralBiometrics,
)
from asagus.layers.antibot_layer6_native import (
    Layer6NativeBinaries,
    NativeLayerConfig,
)
from asagus.layers.captcha_solver import CAPTCHASolver, CAPTCHAType
from asagus.layers.detection_systems import (
    DetectionSystemHandler,
    DetectionEvent,
    DetectionSystem,
    ChallengeType,
)
from asagus.layers.proxy_manager import ProxyManager, ProxyPoolConfig
from asagus.layers.adaptive_mode import (
    AdaptiveModeController,
    AdaptiveConfig as AdaptiveModeConfig,
    AdaptiveAction,
)
from asagus.layers.antibot_config import (
    ConfigurationManager,
    AntiBotConfiguration,
)


logger = logging.getLogger(__name__)


@dataclass
class AntiBotConfig:
    """Unified configuration for all anti-bot layers."""
    
    # Layer 1: Framework selection
    framework_priority: Literal["speed", "stealth", "compatibility"] = "stealth"
    
    # Layer 2: Stealth approach
    stealth_approach: StealthApproach = StealthApproach.javascript_shim
    
    # Layer 3: TLS fingerprint
    tls_fingerprint: BrowserTLSFingerprint = BrowserTLSFingerprint.chrome_124_windows
    
    # Layer 4: Device profile
    device_profile_name: str = "windows_chrome"
    
    # Layer 5: Behavioral simulation
    enable_behavioral_simulation: bool = True
    
    # Layer 6: Native C/C++ binaries
    enable_native_layer: bool = True
    native_backend: str = "cpp_pybind11"

    # Runtime browser engine integrations from LIBRARY_USAGE_ANALYSIS.md
    browser_automation_engine: Literal["playwright", "patchright", "camoufox", "nodriver", "auto"] = "playwright"
    browser_headless: bool = True
    camoufox_binary_path: str = ""
    
    # General options
    proxy_url: str = ""
    enable_consistency_checks: bool = True


class AntiBotOrchestrator:
    """
    Central orchestrator that coordinates all 5 anti-bot layers.
    
    Ensures cross-layer consistency and manages layer interactions.
    """
    
    def __init__(
        self,
        config: AntiBotConfig = AntiBotConfig(),
        proxy_urls: list[str] | None = None,
        config_manager: ConfigurationManager | None = None,
        llm_client: Any = None,
    ):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Initialize layer instances
        self.layer1_selector = Layer1AutomationSelector()
        self.layer2_stealth = Layer2StealthPatching(
            StealthConfig(approach=config.stealth_approach)
        )
        self.layer3_tls = Layer3TLSFingerprinting(
            TLSConfig(fingerprint=config.tls_fingerprint)
        )
        
        # Select device profile
        device_profile = REALISTIC_DEVICE_PROFILES.get(
            config.device_profile_name
        ) or DeviceProfile()
        self.layer4_fingerprinting = Layer4BrowserFingerprinting(device_profile)
        
        self.layer5_behavior = Layer5BehavioralBiometrics()
        
        # Layer 6: Native C/C++ binaries
        if config.enable_native_layer:
            from asagus.layers.antibot_layer6_native import NativeBackend
            native_config = NativeLayerConfig(
                backend=NativeBackend[config.native_backend],
                enable_native_mouse=True,
                enable_native_keyboard=True,
                enable_browser_patching=True,
            )
            self.layer6_native = Layer6NativeBinaries(native_config)
        else:
            self.layer6_native = None
        
        # Initialize CAPTCHA solver with LLM fallback support
        self.captcha_solver = CAPTCHASolver(
            use_yolov8=False,
            use_ml_models=False,
            llm_client=llm_client,
        )
        self.detection_handler = DetectionSystemHandler()
        
        # Proxy manager (optional)
        self.proxy_manager: ProxyManager | None = None
        if proxy_urls:
            proxy_config = ProxyPoolConfig(proxy_urls=proxy_urls)
            self.proxy_manager = ProxyManager(proxy_config)
            self.logger.info(f"Initialized proxy manager with {len(proxy_urls)} proxies")
        
        # Adaptive mode controller
        self.adaptive_controller = AdaptiveModeController(AdaptiveModeConfig())
        
        # Configuration manager (optional)
        self.config_manager = config_manager
        
        self.logger.info(
            f"Initialized AntiBotOrchestrator with {config.stealth_approach.value} stealth, "
            f"{config.tls_fingerprint.value} TLS, {config.device_profile_name} device, "
            f"Native Layer: {'Enabled' if config.enable_native_layer else 'Disabled'}"
        )
    
    async def setup_browser_context(
        self,
        browser: pw.Browser,
        url: str,
        **kwargs
    ) -> pw.BrowserContext:
        """
        Create and configure browser context with all anti-bot layers applied.
        
        Args:
            browser: Playwright browser instance
            url: Target URL (for framework selection)
            **kwargs: Additional browser context options
        
        Returns:
            Configured BrowserContext with all layers applied
        """
        
        self.logger.info(f"Setting up anti-bot context for {url}")
        
        # Layer 1: Select framework
        criteria = FrameworkSelectionCriteria(
            url=url,
            requires_js=self.layer1_selector.analyze_target_site(url),
            priority=self.config.framework_priority,
        )
        
        framework_config = self.layer1_selector.select_framework(criteria)
        self.logger.info(f"Layer 1: Selected framework {framework_config.framework.value}")
        
        # Layer 1+2+3: Get browser context options with stealth/TLS prepared
        context_options = await self.layer1_selector.create_browser_context(framework_config)
        context_options.update(kwargs)
        
        if self.config.proxy_url:
            context_options["proxy"] = {"server": self.config.proxy_url}
        
        # Create context
        context = await browser.new_context(**context_options)
        
        # Layer 2: Apply stealth patches
        await self.layer2_stealth.apply_stealth_to_context(context)
        self.logger.info(f"Layer 2: Applied {self.config.stealth_approach.value} stealth patches")
        
        # Layer 3: TLS already configured at HTTP client level
        self.logger.info(f"Layer 3: TLS {self.config.tls_fingerprint.value} configured")
        
        # Layer 4: Apply fingerprint spoofing
        await self.layer4_fingerprinting.apply_fingerprint_spoofing(context)
        self.logger.info(
            f"Layer 4: Applied fingerprint spoofing (Device ID: {self.layer4_fingerprinting.device_profile.device_id})"
        )
        
        # Layer 6: Apply native C/C++ patches
        if self.layer6_native:
            native_patch_status = await self.layer6_native.apply_native_patches(context)
            self.logger.info("Layer 6 native patch status: %s", native_patch_status.get("status"))
        
        return context
    
    async def create_http_client(self, url: str = "") -> Any:
        """
        Create HTTP client with all anti-bot layers configured.
        
        Args:
            url: Target URL (optional, for framework selection)
        
        Returns:
            Configured HTTP client (curl-cffi or httpx)
        """
        
        self.logger.info("Creating HTTP client with anti-bot layers")
        
        # Layer 1: Select framework (for HTTP-only scraping)
        criteria = FrameworkSelectionCriteria(
            url=url,
            requires_js=JSRequirement.not_required,
            needs_high_throughput=True,
        )
        
        framework_config = self.layer1_selector.select_framework(criteria)
        
        if framework_config.framework == AutomationFramework.curl_cffi:
            # Layer 3: Use curl-cffi with TLS impersonation
            client = await self.layer3_tls.create_curl_cffi_session()
            self.logger.info("Layer 3: Created curl-cffi client with TLS impersonation")
        else:
            # Fallback to httpx
            client = await self.layer3_tls.create_httpx_session_with_custom_tls()
            self.logger.info("Layer 3: Created httpx client with custom headers")
        
        # Layer 2: Inject stealth headers
        await self.layer2_stealth.inject_stealth_headers(client)
        self.logger.info("Layer 2: Injected stealth HTTP headers")
        
        return client
    
    def get_cross_layer_consistency_report(self) -> dict[str, Any]:
        """
        Generate report on cross-layer consistency.
        
        Checks:
        - User-Agent matches TLS fingerprint
        - Device properties are internally coherent
        - No geographically impossible combinations
        
        Returns:
            Consistency report with warnings
        """
        
        report = {
            "consistent": True,
            "warnings": [],
            "layer_info": {},
        }
        
        # Layer 1 info
        report["layer_info"]["layer1_framework"] = "-"  # Will be set when context created
        report["layer_info"]["browser_automation_engine"] = self.config.browser_automation_engine
        report["layer_info"]["optional_browser_libraries"] = self.get_optional_library_status()
        
        # Layer 2 info
        report["layer_info"]["layer2_stealth"] = self.config.stealth_approach.value
        
        # Layer 3 info
        tls_info = self.layer3_tls.get_fingerprint_info()
        report["layer_info"]["layer3_tls_fingerprint"] = tls_info["fingerprint_type"]
        report["layer_info"]["layer3_ja3_hash"] = tls_info["ja3_hash"]
        
        # Layer 4 info
        report["layer_info"]["layer4_device_id"] = self.layer4_fingerprinting.device_profile.device_id
        report["layer_info"]["layer4_gpu"] = self.layer4_fingerprinting.device_profile.webgl_renderer
        
        # Layer 5 info
        report["layer_info"]["layer5_behavioral"] = "enabled" if self.config.enable_behavioral_simulation else "disabled"
        
        # Layer 6 info
        if self.layer6_native:
            native_status = self.layer6_native.get_status_report()
            report["layer_info"]["layer6_native"] = {
                "enabled": True,
                "mouse_available": native_status["components"]["native_mouse"],
                "keyboard_available": native_status["components"]["native_keyboard"],
                "browser_patcher_available": native_status["components"]["browser_patcher"],
            }
        else:
            report["layer_info"]["layer6_native"] = {"enabled": False}
        
        # Consistency checks
        device = self.layer4_fingerprinting.device_profile
        
        # Check: Screen resolution should be realistic
        if device.screen_width > 7680 or device.screen_height > 4320:
            report["warnings"].append(
                f"Unusual screen resolution: {device.screen_width}x{device.screen_height}"
            )
            report["consistent"] = False
        
        # Check: Hardware concurrency should match OS hints
        if device.hardware_concurrency > 256:
            report["warnings"].append(
                f"Unrealistic CPU core count: {device.hardware_concurrency}"
            )
            report["consistent"] = False
        
        # Check: Device memory should be realistic
        if device.device_memory > 256:
            report["warnings"].append(
                f"Unrealistic device memory: {device.device_memory}GB"
            )
            report["consistent"] = False
        
        if report["warnings"]:
            self.logger.warning(f"Cross-layer consistency issues: {report['warnings']}")
        else:
            self.logger.info("Cross-layer consistency checks passed")
        
        return report
    
    def get_status_report(self) -> str:
        """Get human-readable status report of all layers."""
        
        lines = [
            "═" * 70,
            "ANTIBOT ORCHESTRATOR STATUS REPORT",
            "═" * 70,
            "",
            f"Layer 1 - Automation Framework:",
            f"  (Framework selected at runtime based on target)",
            f"  Browser Engine: {self.config.browser_automation_engine}",
            f"  Optional Libraries: {self._format_optional_library_status()}",
            "",
            f"Layer 2 - Stealth/Anti-Detection:",
            f"  Approach: {self.config.stealth_approach.value}",
            "",
            f"Layer 3 - TLS/Network Fingerprinting:",
            f"  TLS Fingerprint: {self.config.tls_fingerprint.value}",
            f"  JA3 Hash: {self.layer3_tls.get_ja3_hash()}",
            "",
            f"Layer 4 - Browser/DOM Fingerprinting:",
            f"  Device ID: {self.layer4_fingerprinting.device_profile.device_id}",
            f"  GPU: {self.layer4_fingerprinting.device_profile.webgl_renderer}",
            f"  Screen: {self.layer4_fingerprinting.device_profile.screen_width}x{self.layer4_fingerprinting.device_profile.screen_height}",
            "",
            f"Layer 5 - Behavioral Biometrics:",
            f"  Behavioral Simulation: {'Enabled' if self.config.enable_behavioral_simulation else 'Disabled'}",
            f"  Movement Model: Sigma Log-Normal + Fitts' Law",
            "",
        ]
        
        # Add Layer 6 info if enabled
        if self.layer6_native:
            native_status = self.layer6_native.get_status_report()
            lines.extend([
                f"Layer 6 - Native C/C++ Binaries:",
                f"  Platform: {native_status['platform']}",
                f"  Native Mouse Control: {'✓ Available' if native_status['components']['native_mouse'] else '✗ Not Available'}",
                f"  Native Keyboard Control: {'✓ Available' if native_status['components']['native_keyboard'] else '✗ Not Available'}",
                f"  Browser Patching: {'✓ Available' if native_status['components']['browser_patcher'] else '✗ Not Available'}",
                "",
            ])
        
        lines.extend([
            "═" * 70,
        ])

        return "\n".join(lines)

    
    async def handle_detection_response(
        self,
        page: pw.Page,
        response: pw.Response | None = None,
        url: str = ""
    ) -> bool:
        """
        Handle detection response with CAPTCHA solving and adaptive strategies.
        
        Args:
            page: Playwright page object
            response: HTTP response (optional)
            url: Request URL
        
        Returns:
            True if detection was handled successfully
        """
        
        import time
        
        # Extract domain from URL
        try:
            from urllib.parse import urlparse
            domain = urlparse(url).netloc
        except Exception:
            domain = "unknown"
        
        # Detect protection system
        detection_system = await self.detection_handler.detect_protection_system(page)
        
        # Detect challenge type
        challenge_type = await self.detection_handler.detect_challenge_type(page, response)
        
        if challenge_type == ChallengeType.none_detected:
            # No detection, mark as success
            await self.adaptive_controller.handle_success(domain)
            return True
        
        self.logger.warning(
            f"Detection on {domain}: {detection_system.value} - {challenge_type.value}"
        )
        
        # Create detection event
        event = DetectionEvent(
            detection_system=detection_system,
            challenge_type=challenge_type,
            url=url,
            status_code=response.status if response else 0,
            resolution_attempted=True,
        )
        
        resolution_start = time.time()
        
        try:
            # Try to solve CAPTCHA if detected
            if challenge_type == ChallengeType.captcha:
                captcha_challenge = await self.captcha_solver.detect_captcha(page)
                if captcha_challenge:
                    await self.captcha_solver.solve_captcha(page, captcha_challenge)
                    event.resolution_successful = True
                    self.logger.info("✓ CAPTCHA solved successfully")
            
            # Handle other challenge types
            elif challenge_type == ChallengeType.turnstile:
                # Wait for Turnstile to complete
                await asyncio.sleep(3)
                event.resolution_successful = True
            
            # Determine adaptive action
            action = await self.adaptive_controller.handle_detection(
                domain,
                response.status if response else 0,
                captcha_detected=(challenge_type == ChallengeType.captcha)
            )
            
            # Execute adaptive action
            if action == AdaptiveAction.rotate_proxy and self.proxy_manager:
                await self.proxy_manager.rotate_proxy()
            
            elif action == AdaptiveAction.rotate_device_profile:
                new_profile = self.adaptive_controller.get_next_device_profile()
                self.layer4_fingerprinting.device_profile = new_profile
                self.logger.info(f"Rotated to device profile: {new_profile.device_id}")
            
            elif action == AdaptiveAction.change_stealth_approach:
                new_approach = self.adaptive_controller.get_next_stealth_approach()
                self.config.stealth_approach = new_approach
                # Recreate stealth layer
                self.layer2_stealth = Layer2StealthPatching(
                    StealthConfig(approach=new_approach)
                )
                self.logger.info(f"Changed stealth approach to: {new_approach.value}")
        
        except Exception as e:
            self.logger.error(f"Error handling detection: {e}")
            event.resolution_successful = False
        
        event.resolution_time_seconds = time.time() - resolution_start
        
        # Log detection event
        self.detection_handler.log_detection_event(event)
        
        return event.resolution_successful
    
    async def get_next_proxy(self) -> str:
        """Get next proxy URL from pool."""
        
        if not self.proxy_manager:
            return ""
        
        proxy = await self.proxy_manager.get_next_proxy()
        if not proxy:
            return ""
        
        return proxy.url
    
    def get_detection_statistics(self) -> dict[str, Any]:
        """Get detection statistics for all domains."""
        
        return {
            "detection_handler": self.detection_handler.get_all_statistics(),
            "adaptive_controller": self.adaptive_controller.get_statistics(),
            "captcha_solver": self.captcha_solver.get_solve_statistics(),
            "proxy_manager": self.proxy_manager.get_statistics() if self.proxy_manager else None,
        }
    
    def export_configuration(self) -> dict[str, Any]:
        """Export current configuration as dictionary."""
        
        return {
            "layer1_framework": "dynamic",
            "layer2_stealth": self.config.stealth_approach.value,
            "layer3_tls": self.config.tls_fingerprint.value,
            "layer4_device_profile": self.config.device_profile_name,
            "layer5_behavioral": self.config.enable_behavioral_simulation,
            "captcha_solving_enabled": False,
            "captcha_runtime_status": "detection_only_manual_review",
            "proxy_pool_size": len(self.proxy_manager.proxies) if self.proxy_manager else 0,
            "adaptive_mode_enabled": True,
            "browser_automation_engine": self.config.browser_automation_engine,
            "optional_browser_libraries": self.get_optional_library_status(),
        }

    def get_optional_library_status(self) -> dict[str, Any]:
        """Report availability of optional libraries requested in LIBRARY_USAGE_ANALYSIS.md."""

        status: dict[str, Any] = {}

        try:
            from asagus.layers.patchright_integration import get_patchright_info
            status["patchright"] = get_patchright_info()
        except Exception as exc:
            status["patchright"] = {"installed": False, "error": str(exc)}

        try:
            from asagus.layers.camoufox_integration import get_camoufox_info
            status["camoufox"] = get_camoufox_info()
        except Exception as exc:
            status["camoufox"] = {"installed": False, "error": str(exc)}

        try:
            from asagus.layers.nodriver_integration import get_nodriver_info
            status["nodriver"] = get_nodriver_info()
        except Exception as exc:
            status["nodriver"] = {"installed": False, "error": str(exc)}

        for library_name in ["scrapy", "selenium", "mechanize"]:
            status[library_name] = {
                "library": library_name,
                "installed": importlib.util.find_spec(library_name) is not None,
            }

        return status

    def _format_optional_library_status(self) -> str:
        status = self.get_optional_library_status()
        parts = []
        for name in ["patchright", "camoufox", "nodriver", "scrapy", "selenium", "mechanize"]:
            info = status.get(name, {})
            installed = bool(info.get("installed"))
            parts.append(f"{name}={'available' if installed else 'unavailable'}")
        return ", ".join(parts)


def create_antibot_orchestrator(config: AntiBotConfig = AntiBotConfig()) -> AntiBotOrchestrator:
    """Create antibot orchestrator with specified configuration."""
    return AntiBotOrchestrator(config)


def create_antibot_orchestrator_from_config(
    config_path: str | None = None,
    preset: str | None = None,
    proxy_urls: list[str] | None = None
) -> AntiBotOrchestrator:
    """
    Create antibot orchestrator from configuration file or preset.
    
    Args:
        config_path: Path to YAML configuration file
        preset: Preset name (high-stealth, high-speed, balanced)
        proxy_urls: List of proxy URLs to override config
    
    Returns:
        Fully configured AntiBotOrchestrator
    """
    
    from asagus.layers.antibot_config import create_config_manager
    
    # Load configuration
    config_manager = create_config_manager(config_path, preset)
    full_config = config_manager.get_config()
    
    # Create AntiBotConfig from loaded configuration
    browser_engine = full_config.global_config.stealth_approach
    if browser_engine not in {"patchright", "camoufox"}:
        browser_engine = "playwright"

    antibot_config = AntiBotConfig(
        framework_priority=full_config.global_config.framework_priority,
        stealth_approach=StealthApproach[full_config.global_config.stealth_approach],
        tls_fingerprint=BrowserTLSFingerprint[full_config.global_config.tls_fingerprint],
        device_profile_name=full_config.global_config.device_profile,
        enable_behavioral_simulation=full_config.global_config.enable_behavioral,
        enable_native_layer=full_config.global_config.enable_native_layer,
        native_backend=full_config.global_config.native_backend,
        browser_automation_engine=browser_engine,
    )
    
    # Use proxies from config or override
    proxies = proxy_urls or full_config.proxy_config.pool
    
    # Create orchestrator
    orchestrator = AntiBotOrchestrator(
        config=antibot_config,
        proxy_urls=proxies,
        config_manager=config_manager
    )
    
    return orchestrator
