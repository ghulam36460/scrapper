"""
Mode Control Layer - Coordinates existing layers based on selected scraping mode.

This layer provides a mode system that orchestrates existing layers without
modifying their implementation. Each mode configures layer behavior differently.

Modes:
- balanced: Default mix of speed and completeness
- fast: Fast scraping with minimal overhead
- deep: Maximum thoroughness, all checks, all validations
- deep_agent: Deep mode with AI agent assistance
- parallel: Parallel processing for high throughput
- research: Research-focused with comprehensive data gathering
- quick: Quick mode for rapid results (NEW)
- stealth: Anti-detection focused scraping (NEW)
- advanced: Combines all modes simultaneously (NEW)
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Mode(str, Enum):
    """Available scraping modes."""
    BALANCED = "balanced"
    FAST = "fast"
    DEEP = "deep"
    DEEP_AGENT = "deep_agent"
    PARALLEL = "parallel"
    RESEARCH = "research"
    QUICK = "quick"  # NEW
    STEALTH = "stealth"  # NEW
    ADVANCED = "advanced"  # NEW - combines all modes


class LayerConfig(BaseModel):
    """Configuration for a single layer in a specific mode."""
    enabled: bool = True
    priority: int = 0  # Higher = processed first
    max_iterations: int = 1
    timeout_seconds: int = 30
    retry_count: int = 1
    options: dict[str, Any] = Field(default_factory=dict)


class ModeLayerConfig(BaseModel):
    """Configuration mapping layers to their settings for a specific mode."""
    policy: LayerConfig = Field(default_factory=LayerConfig)
    crawl_control: LayerConfig = Field(default_factory=LayerConfig)
    compliance: LayerConfig = Field(default_factory=LayerConfig)
    fetch: LayerConfig = Field(default_factory=LayerConfig)
    extraction: LayerConfig = Field(default_factory=LayerConfig)
    enrichment: LayerConfig = Field(default_factory=LayerConfig)
    storage: LayerConfig = Field(default_factory=LayerConfig)
    indexing: LayerConfig = Field(default_factory=LayerConfig)
    retrieval: LayerConfig = Field(default_factory=LayerConfig)
    ai_app: LayerConfig = Field(default_factory=LayerConfig)
    analytics: LayerConfig = Field(default_factory=LayerConfig)
    browser: LayerConfig = Field(default_factory=LayerConfig)
    browser_actions: LayerConfig = Field(default_factory=LayerConfig)
    challenge_detector: LayerConfig = Field(default_factory=LayerConfig)
    compute_accelerator: LayerConfig = Field(default_factory=LayerConfig)
    discovery: LayerConfig = Field(default_factory=LayerConfig)
    dom_tools: LayerConfig = Field(default_factory=LayerConfig)
    fingerprint_advanced: LayerConfig = Field(default_factory=LayerConfig)
    geoint: LayerConfig = Field(default_factory=LayerConfig)
    graph: LayerConfig = Field(default_factory=LayerConfig)
    human_behavior: LayerConfig = Field(default_factory=LayerConfig)
    nlp_intelligence: LayerConfig = Field(default_factory=LayerConfig)
    observability: LayerConfig = Field(default_factory=LayerConfig)
    osint: LayerConfig = Field(default_factory=LayerConfig)
    proxy: LayerConfig = Field(default_factory=LayerConfig)
    resource_governor: LayerConfig = Field(default_factory=LayerConfig)
    search_index: LayerConfig = Field(default_factory=LayerConfig)
    throughput: LayerConfig = Field(default_factory=LayerConfig)
    vision: LayerConfig = Field(default_factory=LayerConfig)


# Default configurations for each mode
DEFAULT_BALANCED_CONFIG = ModeLayerConfig(
    policy=LayerConfig(enabled=True, priority=10, timeout_seconds=30),
    crawl_control=LayerConfig(enabled=True, priority=9, timeout_seconds=60),
    compliance=LayerConfig(enabled=True, priority=8, timeout_seconds=30),
    fetch=LayerConfig(enabled=True, priority=7, timeout_seconds=45),
    extraction=LayerConfig(enabled=True, priority=6, timeout_seconds=60),
    enrichment=LayerConfig(enabled=True, priority=5, timeout_seconds=45),
    storage=LayerConfig(enabled=True, priority=4, timeout_seconds=30),
    indexing=LayerConfig(enabled=True, priority=3, timeout_seconds=30),
    retrieval=LayerConfig(enabled=True, priority=2, timeout_seconds=30),
    ai_app=LayerConfig(enabled=True, priority=1, timeout_seconds=120),
)

DEFAULT_FAST_CONFIG = ModeLayerConfig(
    policy=LayerConfig(enabled=True, priority=10, timeout_seconds=15),
    crawl_control=LayerConfig(enabled=True, priority=9, timeout_seconds=30),
    compliance=LayerConfig(enabled=True, priority=8, timeout_seconds=15),
    fetch=LayerConfig(enabled=True, priority=7, timeout_seconds=20),
    extraction=LayerConfig(enabled=True, priority=6, timeout_seconds=30),
    enrichment=LayerConfig(enabled=False, priority=0),  # Disabled for speed
    storage=LayerConfig(enabled=True, priority=4, timeout_seconds=15),
    indexing=LayerConfig(enabled=True, priority=3, timeout_seconds=15),
    retrieval=LayerConfig(enabled=True, priority=2, timeout_seconds=15),
    ai_app=LayerConfig(enabled=False, priority=0),  # Disabled for speed
)

DEFAULT_DEEP_CONFIG = ModeLayerConfig(
    policy=LayerConfig(enabled=True, priority=10, timeout_seconds=60),
    crawl_control=LayerConfig(enabled=True, priority=9, timeout_seconds=120),
    compliance=LayerConfig(enabled=True, priority=8, timeout_seconds=60),
    fetch=LayerConfig(enabled=True, priority=7, timeout_seconds=90, retry_count=3),
    extraction=LayerConfig(enabled=True, priority=6, timeout_seconds=120, max_iterations=3),
    enrichment=LayerConfig(enabled=True, priority=5, timeout_seconds=90, max_iterations=2),
    storage=LayerConfig(enabled=True, priority=4, timeout_seconds=60),
    indexing=LayerConfig(enabled=True, priority=3, timeout_seconds=60),
    retrieval=LayerConfig(enabled=True, priority=2, timeout_seconds=60),
    ai_app=LayerConfig(enabled=True, priority=1, timeout_seconds=180, max_iterations=2),
    challenge_detector=LayerConfig(enabled=True, priority=11, timeout_seconds=60),
    fingerprint_advanced=LayerConfig(enabled=True, priority=12, timeout_seconds=45),
)

DEFAULT_DEEP_AGENT_CONFIG = ModeLayerConfig(
    policy=LayerConfig(enabled=True, priority=10, timeout_seconds=60),
    crawl_control=LayerConfig(enabled=True, priority=9, timeout_seconds=120),
    compliance=LayerConfig(enabled=True, priority=8, timeout_seconds=60),
    fetch=LayerConfig(enabled=True, priority=7, timeout_seconds=90, retry_count=3),
    extraction=LayerConfig(enabled=True, priority=6, timeout_seconds=120, max_iterations=3),
    enrichment=LayerConfig(enabled=True, priority=5, timeout_seconds=90, max_iterations=2),
    storage=LayerConfig(enabled=True, priority=4, timeout_seconds=60),
    indexing=LayerConfig(enabled=True, priority=3, timeout_seconds=60),
    retrieval=LayerConfig(enabled=True, priority=2, timeout_seconds=60),
    ai_app=LayerConfig(enabled=True, priority=1, timeout_seconds=300, max_iterations=3),
    challenge_detector=LayerConfig(enabled=True, priority=11, timeout_seconds=60),
    fingerprint_advanced=LayerConfig(enabled=True, priority=12, timeout_seconds=45),
    nlp_intelligence=LayerConfig(enabled=True, priority=13, timeout_seconds=120),
)

DEFAULT_PARALLEL_CONFIG = ModeLayerConfig(
    policy=LayerConfig(enabled=True, priority=10, timeout_seconds=30),
    crawl_control=LayerConfig(enabled=True, priority=9, timeout_seconds=60, max_iterations=5),
    compliance=LayerConfig(enabled=True, priority=8, timeout_seconds=30),
    fetch=LayerConfig(enabled=True, priority=7, timeout_seconds=45, max_iterations=3),
    extraction=LayerConfig(enabled=True, priority=6, timeout_seconds=60),
    enrichment=LayerConfig(enabled=True, priority=5, timeout_seconds=45),
    storage=LayerConfig(enabled=True, priority=4, timeout_seconds=30),
    indexing=LayerConfig(enabled=True, priority=3, timeout_seconds=30),
    retrieval=LayerConfig(enabled=True, priority=2, timeout_seconds=30),
    ai_app=LayerConfig(enabled=True, priority=1, timeout_seconds=120),
    throughput=LayerConfig(enabled=True, priority=14, timeout_seconds=30),
)

DEFAULT_RESEARCH_CONFIG = ModeLayerConfig(
    policy=LayerConfig(enabled=True, priority=10, timeout_seconds=60),
    crawl_control=LayerConfig(enabled=True, priority=9, timeout_seconds=120),
    compliance=LayerConfig(enabled=True, priority=8, timeout_seconds=60),
    fetch=LayerConfig(enabled=True, priority=7, timeout_seconds=90, retry_count=3),
    extraction=LayerConfig(enabled=True, priority=6, timeout_seconds=120, max_iterations=3),
    enrichment=LayerConfig(enabled=True, priority=5, timeout_seconds=90, max_iterations=2),
    storage=LayerConfig(enabled=True, priority=4, timeout_seconds=60),
    indexing=LayerConfig(enabled=True, priority=3, timeout_seconds=60),
    retrieval=LayerConfig(enabled=True, priority=2, timeout_seconds=60),
    ai_app=LayerConfig(enabled=True, priority=1, timeout_seconds=180, max_iterations=2),
    analytics=LayerConfig(enabled=True, priority=13, timeout_seconds=120),
    osint=LayerConfig(enabled=True, priority=14, timeout_seconds=120),
    graph=LayerConfig(enabled=True, priority=15, timeout_seconds=120),
)

# NEW: Quick mode - rapid results with minimal overhead
DEFAULT_QUICK_CONFIG = ModeLayerConfig(
    policy=LayerConfig(enabled=True, priority=10, timeout_seconds=10),
    crawl_control=LayerConfig(enabled=True, priority=9, timeout_seconds=15),
    compliance=LayerConfig(enabled=True, priority=8, timeout_seconds=10),
    fetch=LayerConfig(enabled=True, priority=7, timeout_seconds=15),
    extraction=LayerConfig(enabled=True, priority=6, timeout_seconds=20),
    enrichment=LayerConfig(enabled=False, priority=0),
    storage=LayerConfig(enabled=True, priority=4, timeout_seconds=10),
    indexing=LayerConfig(enabled=False, priority=0),
    retrieval=LayerConfig(enabled=True, priority=2, timeout_seconds=10),
    ai_app=LayerConfig(enabled=False, priority=0),
)

# NEW: Stealth mode - anti-detection focused
DEFAULT_STEALTH_CONFIG = ModeLayerConfig(
    policy=LayerConfig(enabled=True, priority=10, timeout_seconds=30),
    crawl_control=LayerConfig(enabled=True, priority=9, timeout_seconds=60),
    compliance=LayerConfig(enabled=True, priority=8, timeout_seconds=30),
    fetch=LayerConfig(enabled=True, priority=7, timeout_seconds=45, retry_count=2),
    extraction=LayerConfig(enabled=True, priority=6, timeout_seconds=60),
    enrichment=LayerConfig(enabled=True, priority=5, timeout_seconds=45),
    storage=LayerConfig(enabled=True, priority=4, timeout_seconds=30),
    indexing=LayerConfig(enabled=True, priority=3, timeout_seconds=30),
    retrieval=LayerConfig(enabled=True, priority=2, timeout_seconds=30),
    ai_app=LayerConfig(enabled=True, priority=1, timeout_seconds=120),
    human_behavior=LayerConfig(enabled=True, priority=15, timeout_seconds=60),
    fingerprint_advanced=LayerConfig(enabled=True, priority=16, timeout_seconds=45),
    proxy=LayerConfig(enabled=True, priority=17, timeout_seconds=30),
    browser=LayerConfig(enabled=True, priority=18, timeout_seconds=30),
)

# NEW: Advanced mode - combines all modes
DEFAULT_ADVANCED_CONFIG = ModeLayerConfig(
    policy=LayerConfig(enabled=True, priority=10, timeout_seconds=60, max_iterations=2),
    crawl_control=LayerConfig(enabled=True, priority=9, timeout_seconds=120, max_iterations=3),
    compliance=LayerConfig(enabled=True, priority=8, timeout_seconds=60),
    fetch=LayerConfig(enabled=True, priority=7, timeout_seconds=90, retry_count=3, max_iterations=2),
    extraction=LayerConfig(enabled=True, priority=6, timeout_seconds=120, max_iterations=3),
    enrichment=LayerConfig(enabled=True, priority=5, timeout_seconds=90, max_iterations=2),
    storage=LayerConfig(enabled=True, priority=4, timeout_seconds=60),
    indexing=LayerConfig(enabled=True, priority=3, timeout_seconds=60),
    retrieval=LayerConfig(enabled=True, priority=2, timeout_seconds=60),
    ai_app=LayerConfig(enabled=True, priority=1, timeout_seconds=300, max_iterations=3),
    analytics=LayerConfig(enabled=True, priority=13, timeout_seconds=120),
    osint=LayerConfig(enabled=True, priority=14, timeout_seconds=120),
    graph=LayerConfig(enabled=True, priority=15, timeout_seconds=120),
    challenge_detector=LayerConfig(enabled=True, priority=16, timeout_seconds=60),
    fingerprint_advanced=LayerConfig(enabled=True, priority=17, timeout_seconds=45),
    human_behavior=LayerConfig(enabled=True, priority=18, timeout_seconds=60),
    proxy=LayerConfig(enabled=True, priority=19, timeout_seconds=30),
    browser=LayerConfig(enabled=True, priority=20, timeout_seconds=30),
    nlp_intelligence=LayerConfig(enabled=True, priority=21, timeout_seconds=120),
    vision=LayerConfig(enabled=True, priority=22, timeout_seconds=90),
    compute_accelerator=LayerConfig(enabled=True, priority=23, timeout_seconds=60),
    throughput=LayerConfig(enabled=True, priority=24, timeout_seconds=30),
    observability=LayerConfig(enabled=True, priority=25, timeout_seconds=30),
)


MODE_CONFIGS: dict[Mode, ModeLayerConfig] = {
    Mode.BALANCED: DEFAULT_BALANCED_CONFIG,
    Mode.FAST: DEFAULT_FAST_CONFIG,
    Mode.DEEP: DEFAULT_DEEP_CONFIG,
    Mode.DEEP_AGENT: DEFAULT_DEEP_AGENT_CONFIG,
    Mode.PARALLEL: DEFAULT_PARALLEL_CONFIG,
    Mode.RESEARCH: DEFAULT_RESEARCH_CONFIG,
    Mode.QUICK: DEFAULT_QUICK_CONFIG,
    Mode.STEALTH: DEFAULT_STEALTH_CONFIG,
    Mode.ADVANCED: DEFAULT_ADVANCED_CONFIG,
}


class ModeOrchestrator:
    """
    Orchestrates layer execution based on selected mode.
    
    This class provides mode-specific configurations and coordinates
    which layers are enabled and how they behave for each mode.
    """

    def __init__(self, mode: Mode = Mode.BALANCED):
        self.mode = mode
        self.config = MODE_CONFIGS.get(mode, DEFAULT_BALANCED_CONFIG)

    def get_layer_config(self, layer_name: str) -> LayerConfig:
        """Get configuration for a specific layer in the current mode."""
        return getattr(self.config, layer_name, LayerConfig(enabled=False))

    def get_enabled_layers(self) -> list[tuple[str, LayerConfig]]:
        """Get all enabled layers sorted by priority (highest first)."""
        enabled = []
        for layer_name, layer_config in self.config.model_dump().items():
            if layer_config.get("enabled", False):
                enabled.append((layer_name, LayerConfig(**layer_config)))
        enabled.sort(key=lambda x: x[1].priority, reverse=True)
        return enabled

    def get_mode_description(self) -> str:
        """Get human-readable description of the current mode."""
        descriptions = {
            Mode.BALANCED: "Balanced mode: Default mix of speed and completeness",
            Mode.FAST: "Fast mode: Quick scraping with minimal overhead",
            Mode.DEEP: "Deep mode: Maximum thoroughness with all checks enabled",
            Mode.DEEP_AGENT: "Deep Agent mode: Deep scanning with AI agent assistance",
            Mode.PARALLEL: "Parallel mode: High throughput with concurrent processing",
            Mode.RESEARCH: "Research mode: Comprehensive data gathering for research",
            Mode.QUICK: "Quick mode: Rapid results for time-sensitive needs",
            Mode.STEALTH: "Stealth mode: Anti-detection focused scraping",
            Mode.ADVANCED: "Advanced mode: Combines all modes for maximum coverage",
        }
        return descriptions.get(self.mode, "Unknown mode")

    def is_layer_enabled(self, layer_name: str) -> bool:
        """Check if a specific layer is enabled in the current mode."""
        config = self.get_layer_config(layer_name)
        return config.enabled

    def get_timeout_for_layer(self, layer_name: str) -> int:
        """Get timeout value for a specific layer in the current mode."""
        config = self.get_layer_config(layer_name)
        return config.timeout_seconds

    def should_retry_layer(self, layer_name: str) -> bool:
        """Check if a layer should retry on failure in the current mode."""
        config = self.get_layer_config(layer_name)
        return config.retry_count > 1

    def get_layer_priority(self, layer_name: str) -> int:
        """Get priority of a layer in the current mode."""
        config = self.get_layer_config(layer_name)
        return config.priority


def get_mode_orchestrator(mode: Mode = Mode.BALANCED) -> ModeOrchestrator:
    """Factory function to create a ModeOrchestrator instance."""
    return ModeOrchestrator(mode=mode)


def get_mode_config(mode: Mode) -> ModeLayerConfig:
    """Get the configuration for a specific mode."""
    return MODE_CONFIGS.get(mode, DEFAULT_BALANCED_CONFIG)


def list_available_modes() -> list[dict[str, Any]]:
    """List all available modes with their descriptions."""
    return [
        {"mode": m.value, "description": ModeOrchestrator(m).get_mode_description()}
        for m in Mode
    ]