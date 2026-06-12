"""
Configuration Management System
================================
Flexible configuration of all evasion layers with presets and validation.

From Requirements 17:
- Load configuration from YAML files
- Support configuration hierarchy (global → domain-specific → runtime)
- Validate configuration parameters
- Support environment variable substitution
- Hot reload when config file changes
- Export configuration as JSON
- Provide configuration presets (high-stealth, high-speed, balanced)
- Document valid ranges and defaults

Configuration Structure:
```yaml
global:
  framework_priority: stealth  # speed, stealth, compatibility
  stealth_approach: camoufox   # javascript_shim, patchright, camoufox, etc.
  tls_fingerprint: chrome_124_windows
  device_profile: windows_chrome
  enable_behavioral: true
  
domains:
  example.com:
    framework_priority: speed
    stealth_approach: patchright
    
proxies:
  pool:
    - "http://user:pass@proxy1.com:8080"
    - "http://user:pass@proxy2.com:8080"
  rotation_interval: 500
  
adaptive:
  threshold_light: 3
  threshold_medium: 5
  threshold_heavy: 7
```
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Literal

import yaml

from asagus.layers.antibot_layer2_stealth import StealthApproach
from asagus.layers.antibot_layer3_tls import BrowserTLSFingerprint


logger = logging.getLogger(__name__)


@dataclass
class GlobalConfig:
    """Global antibot configuration."""
    framework_priority: Literal["speed", "stealth", "compatibility"] = "stealth"
    stealth_approach: str = "javascript_shim"
    tls_fingerprint: str = "chrome_124_windows"
    device_profile: str = "windows_chrome"
    enable_behavioral: bool = True
    enable_captcha_solving: bool = True
    enable_native_layer: bool = True
    native_backend: str = "cpp_pybind11"
    
    # Validation
    def validate(self) -> list[str]:
        """Validate configuration and return list of errors."""
        errors = []
        
        if self.framework_priority not in ["speed", "stealth", "compatibility"]:
            errors.append(
                f"Invalid framework_priority: {self.framework_priority}. "
                f"Must be: speed, stealth, or compatibility"
            )
        
        valid_stealth = [
            "javascript_shim", "patchright", "camoufox", 
            "cloak_browser", "binary_patch"
        ]
        if self.stealth_approach not in valid_stealth:
            errors.append(
                f"Invalid stealth_approach: {self.stealth_approach}. "
                f"Must be one of: {', '.join(valid_stealth)}"
            )
        
        valid_tls = [
            "chrome_124_windows", "chrome_124_macos", "chrome_124_linux",
            "firefox_125_windows", "firefox_125_macos", "edge_124_windows",
            "safari_17_macos"
        ]
        if self.tls_fingerprint not in valid_tls:
            errors.append(
                f"Invalid tls_fingerprint: {self.tls_fingerprint}. "
                f"Must be one of: {', '.join(valid_tls)}"
            )
        
        valid_profiles = ["windows_chrome", "macos_chrome", "linux_firefox"]
        if self.device_profile not in valid_profiles:
            errors.append(
                f"Invalid device_profile: {self.device_profile}. "
                f"Must be one of: {', '.join(valid_profiles)}"
            )
        
        return errors


@dataclass
class ProxyConfig:
    """Proxy pool configuration."""
    pool: list[str] = field(default_factory=list)
    rotation_interval: int = 500
    response_time_threshold: float = 3.0
    max_consecutive_failures: int = 3
    verify_geolocation: bool = True
    
    def validate(self) -> list[str]:
        """Validate proxy configuration."""
        errors = []
        
        if self.rotation_interval < 1:
            errors.append("rotation_interval must be >= 1")
        
        if self.response_time_threshold < 0.1:
            errors.append("response_time_threshold must be >= 0.1")
        
        if self.max_consecutive_failures < 1:
            errors.append("max_consecutive_failures must be >= 1")
        
        return errors


@dataclass
class AdaptiveConfig:
    """Adaptive mode configuration."""
    threshold_light: int = 3
    threshold_medium: int = 5
    threshold_heavy: int = 7
    initial_backoff_seconds: float = 1.0
    max_backoff_seconds: float = 60.0
    success_reset_threshold: int = 100
    
    def validate(self) -> list[str]:
        """Validate adaptive configuration."""
        errors = []
        
        if self.threshold_light >= self.threshold_medium:
            errors.append("threshold_light must be < threshold_medium")
        
        if self.threshold_medium >= self.threshold_heavy:
            errors.append("threshold_medium must be < threshold_heavy")
        
        if self.initial_backoff_seconds < 0:
            errors.append("initial_backoff_seconds must be >= 0")
        
        if self.max_backoff_seconds < self.initial_backoff_seconds:
            errors.append("max_backoff_seconds must be >= initial_backoff_seconds")
        
        return errors


@dataclass
class AntiBotConfiguration:
    """Complete antibot system configuration."""
    global_config: GlobalConfig = field(default_factory=GlobalConfig)
    proxy_config: ProxyConfig = field(default_factory=ProxyConfig)
    adaptive_config: AdaptiveConfig = field(default_factory=AdaptiveConfig)
    domain_overrides: dict[str, GlobalConfig] = field(default_factory=dict)
    
    def validate(self) -> list[str]:
        """Validate entire configuration."""
        errors = []
        
        errors.extend(self.global_config.validate())
        errors.extend(self.proxy_config.validate())
        errors.extend(self.adaptive_config.validate())
        
        # Validate domain overrides
        for domain, config in self.domain_overrides.items():
            domain_errors = config.validate()
            if domain_errors:
                errors.extend([f"Domain {domain}: {err}" for err in domain_errors])
        
        return errors
    
    def get_config_for_domain(self, domain: str) -> GlobalConfig:
        """Get configuration for specific domain (with overrides)."""
        
        if domain in self.domain_overrides:
            return self.domain_overrides[domain]
        
        return self.global_config


class ConfigurationManager:
    """
    Manage antibot configuration with validation and hot reloading.
    
    Features:
    - Load from YAML files
    - Environment variable substitution
    - Configuration validation
    - Hot reload support
    - Preset configurations
    - Export to JSON
    """
    
    # Preset configurations
    PRESETS = {
        "high-stealth": {
            "global": {
                "framework_priority": "stealth",
                "stealth_approach": "camoufox",
                "tls_fingerprint": "chrome_124_windows",
                "device_profile": "windows_chrome",
                "enable_behavioral": True,
                "enable_captcha_solving": True,
                "enable_native_layer": True,
                "native_backend": "cpp_pybind11",
            },
            "adaptive": {
                "threshold_light": 2,
                "threshold_medium": 4,
                "threshold_heavy": 6,
            },
            "description": "Maximum stealth - Camoufox binary patches, full behavioral simulation"
        },
        
        "high-speed": {
            "global": {
                "framework_priority": "speed",
                "stealth_approach": "javascript_shim",
                "tls_fingerprint": "chrome_124_windows",
                "device_profile": "windows_chrome",
                "enable_behavioral": False,
                "enable_captcha_solving": False,
                "enable_native_layer": False,  # Disabled for speed
                "native_backend": "cpp_pybind11",
            },
            "adaptive": {
                "threshold_light": 5,
                "threshold_medium": 10,
                "threshold_heavy": 15,
            },
            "description": "Maximum speed - Minimal stealth, no behavioral simulation"
        },
        
        "balanced": {
            "global": {
                "framework_priority": "stealth",
                "stealth_approach": "patchright",
                "tls_fingerprint": "chrome_124_windows",
                "device_profile": "windows_chrome",
                "enable_behavioral": True,
                "enable_captcha_solving": True,
                "enable_native_layer": True,
                "native_backend": "cpp_pybind11",
            },
            "adaptive": {
                "threshold_light": 3,
                "threshold_medium": 5,
                "threshold_heavy": 7,
            },
            "description": "Balanced - Good stealth with reasonable performance"
        }
    }
    
    def __init__(self, config_path: str | None = None):
        self.logger = logging.getLogger(__name__)
        self.config_path = config_path
        self.config = AntiBotConfiguration()
        
        if config_path:
            self.load_from_file(config_path)
    
    def load_from_file(self, path: str) -> None:
        """
        Load configuration from YAML file.
        
        Args:
            path: Path to YAML configuration file
        """
        
        self.logger.info(f"Loading configuration from {path}")
        
        try:
            with open(path, 'r') as f:
                data = yaml.safe_load(f)
            
            # Substitute environment variables
            data = self._substitute_env_vars(data)
            
            # Parse configuration
            self.config = self._parse_config_dict(data)
            
            # Validate
            errors = self.config.validate()
            if errors:
                self.logger.error(f"Configuration validation errors: {errors}")
                raise ValueError(f"Invalid configuration: {errors}")
            
            self.logger.info("Configuration loaded and validated successfully")
        
        except FileNotFoundError:
            self.logger.warning(f"Config file not found: {path}, using defaults")
        
        except Exception as e:
            self.logger.error(f"Error loading configuration: {e}")
            raise
    
    def load_preset(self, preset_name: str) -> None:
        """
        Load preset configuration.
        
        Args:
            preset_name: Name of preset (high-stealth, high-speed, balanced)
        """
        
        if preset_name not in self.PRESETS:
            raise ValueError(
                f"Unknown preset: {preset_name}. "
                f"Available: {', '.join(self.PRESETS.keys())}"
            )
        
        preset = self.PRESETS[preset_name]
        self.logger.info(f"Loading preset '{preset_name}': {preset['description']}")
        
        self.config = self._parse_config_dict(preset)
    
    def _parse_config_dict(self, data: dict[str, Any]) -> AntiBotConfiguration:
        """Parse configuration dictionary into dataclass."""
        
        config = AntiBotConfiguration()
        
        # Parse global config
        if "global" in data:
            config.global_config = GlobalConfig(**data["global"])
        
        # Parse proxy config
        if "proxies" in data:
            config.proxy_config = ProxyConfig(**data["proxies"])
        
        # Parse adaptive config
        if "adaptive" in data:
            config.adaptive_config = AdaptiveConfig(**data["adaptive"])
        
        # Parse domain overrides
        if "domains" in data:
            for domain, domain_config in data["domains"].items():
                config.domain_overrides[domain] = GlobalConfig(**domain_config)
        
        return config
    
    def _substitute_env_vars(self, data: Any) -> Any:
        """Recursively substitute environment variables in configuration."""
        
        if isinstance(data, dict):
            return {k: self._substitute_env_vars(v) for k, v in data.items()}
        
        elif isinstance(data, list):
            return [self._substitute_env_vars(item) for item in data]
        
        elif isinstance(data, str):
            # Replace ${VAR_NAME} with environment variable
            if data.startswith("${") and data.endswith("}"):
                var_name = data[2:-1]
                return os.getenv(var_name, data)
        
        return data
    
    def export_to_json(self) -> str:
        """Export configuration as JSON string."""
        
        return json.dumps(
            asdict(self.config),
            indent=2,
            default=str
        )
    
    def export_to_dict(self) -> dict[str, Any]:
        """Export configuration as dictionary."""
        return asdict(self.config)
    
    def hot_reload(self) -> None:
        """Hot reload configuration from file."""
        
        if not self.config_path:
            self.logger.warning("No config path set, cannot hot reload")
            return
        
        self.logger.info("Hot reloading configuration...")
        self.load_from_file(self.config_path)
    
    def get_config(self) -> AntiBotConfiguration:
        """Get current configuration."""
        return self.config
    
    def get_config_for_domain(self, domain: str) -> GlobalConfig:
        """Get configuration for specific domain."""
        return self.config.get_config_for_domain(domain)
    
    @classmethod
    def get_available_presets(cls) -> dict[str, str]:
        """Get available configuration presets."""
        return {
            name: preset["description"]
            for name, preset in cls.PRESETS.items()
        }
    
    @classmethod
    def get_configuration_schema(cls) -> dict[str, Any]:
        """Get configuration schema documentation."""
        
        return {
            "global": {
                "framework_priority": {
                    "type": "string",
                    "valid_values": ["speed", "stealth", "compatibility"],
                    "default": "stealth",
                    "description": "Framework selection priority"
                },
                "stealth_approach": {
                    "type": "string",
                    "valid_values": [
                        "javascript_shim", "patchright", "camoufox",
                        "cloak_browser", "binary_patch"
                    ],
                    "default": "javascript_shim",
                    "description": "Stealth patching approach (Layer 2)"
                },
                "tls_fingerprint": {
                    "type": "string",
                    "valid_values": [
                        "chrome_124_windows", "chrome_124_macos", "chrome_124_linux",
                        "firefox_125_windows", "firefox_125_macos",
                        "edge_124_windows", "safari_17_macos"
                    ],
                    "default": "chrome_124_windows",
                    "description": "TLS fingerprint to impersonate (Layer 3)"
                },
                "device_profile": {
                    "type": "string",
                    "valid_values": ["windows_chrome", "macos_chrome", "linux_firefox"],
                    "default": "windows_chrome",
                    "description": "Device profile for fingerprinting (Layer 4)"
                },
                "enable_behavioral": {
                    "type": "boolean",
                    "default": True,
                    "description": "Enable behavioral biometrics simulation (Layer 5)"
                },
                "enable_captcha_solving": {
                    "type": "boolean",
                    "default": True,
                    "description": "Enable CAPTCHA solving"
                },
                "enable_native_layer": {
                    "type": "boolean",
                    "default": True,
                    "description": "Enable native C/C++ binary layer (Layer 6)"
                },
                "native_backend": {
                    "type": "string",
                    "valid_values": ["python_ctypes", "cython", "cpp_pybind11", "rust_ffi"],
                    "default": "cpp_pybind11",
                    "description": "Native backend for Layer 6"
                }
            },
            "proxies": {
                "pool": {
                    "type": "list[string]",
                    "default": [],
                    "description": "List of proxy URLs"
                },
                "rotation_interval": {
                    "type": "integer",
                    "default": 500,
                    "range": "1-10000",
                    "description": "Rotate proxy after N requests"
                },
                "response_time_threshold": {
                    "type": "float",
                    "default": 3.0,
                    "range": "0.1-60.0",
                    "description": "Slow proxy threshold (seconds)"
                }
            },
            "adaptive": {
                "threshold_light": {
                    "type": "integer",
                    "default": 3,
                    "range": "1-100",
                    "description": "Rotate proxy after N detections"
                },
                "threshold_medium": {
                    "type": "integer",
                    "default": 5,
                    "range": "1-100",
                    "description": "Rotate device profile after N detections"
                },
                "threshold_heavy": {
                    "type": "integer",
                    "default": 7,
                    "range": "1-100",
                    "description": "Change stealth approach after N detections"
                }
            }
        }


def create_config_manager(config_path: str | None = None, preset: str | None = None) -> ConfigurationManager:
    """
    Create configuration manager.
    
    Args:
        config_path: Path to YAML config file (optional)
        preset: Preset name to load (optional)
    
    Returns:
        Initialized ConfigurationManager
    """
    
    manager = ConfigurationManager(config_path)
    
    if preset:
        manager.load_preset(preset)
    
    return manager
