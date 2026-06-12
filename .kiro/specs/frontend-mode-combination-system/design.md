# Design Document: Frontend Mode Combination System

## Overview

The Frontend Mode Combination System extends the existing ASAGUS Scraper v3 architecture to provide:

1. **User-Friendly Mode Selection Interface**: Dropdown controls for selecting scraping depth modes and antibot stealth levels simultaneously
2. **Automatic Hardware Acceleration**: Detection and utilization of GPU/TPU/DPU resources for CAPTCHA solving and ML inference
3. **Real-Time System Feedback**: Hardware status indicators and performance impact displays

### System Context

The system integrates with:
- **Frontend**: Next.js application with single-file page.tsx component (1,622 lines)
- **Backend**: FastAPI application with main.py orchestrating all layers
- **Existing Antibot System**: 5-layer antibot orchestrator with preset configurations
- **Hardware Detection**: Compute accelerator module with GPU/TPU detection skeleton

### Design Philosophy

This feature follows the "additive enhancement" pattern:
- **Zero Breaking Changes**: All existing functionality remains unchanged
- **Graceful Degradation**: System works without GPU when hardware is unavailable
- **Progressive Enhancement**: New UI controls enhance but don't replace existing workflows
- **Backend-First Validation**: Frontend displays options; backend enforces rules

## Architecture

### High-Level System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         FRONTEND (Next.js)                          │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  page.tsx (Modified)                                         │   │
│  │  ┌─────────────────┐  ┌──────────────────┐  ┌────────────┐  │   │
│  │  │ Mode Selection  │  │ Hardware Status  │  │Performance │  │   │
│  │  │   Component     │  │   Indicator      │  │ Indicator  │  │   │
│  │  └────────┬────────┘  └────────┬─────────┘  └──────┬─────┘  │   │
│  └───────────┼────────────────────┼────────────────────┼────────┘   │
└──────────────┼────────────────────┼────────────────────┼────────────┘
               │                    │                    │
               │ GET /api/modes/    │ GET /api/hardware/ │
               │ available          │ status             │
               │                    │                    │
               │ POST /api/jobs     │                    │
               │ {mode, preset}     │                    │
               ▼                    ▼                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        BACKEND (FastAPI)                            │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  main.py (Modified)                                          │   │
│  │  ┌──────────────────────────────────────────────────────────┐│   │
│  │  │  New Endpoints:                                          ││   │
│  │  │  • /api/modes/available → Mode Validator                 ││   │
│  │  │  • /api/hardware/status → Hardware Detector              ││   │
│  │  │  • POST /api/jobs (extended with antibot_preset field)   ││   │
│  │  └──────────────────────────────────────────────────────────┘│   │
│  └──────────┬────────────────────┬──────────────────┬────────────┘   │
│             │                    │                  │                │
│             ▼                    ▼                  ▼                │
│  ┌────────────────────┐ ┌─────────────────┐ ┌──────────────────┐   │
│  │ Configuration      │ │ Hardware        │ │ Mode             │   │
│  │ Manager            │ │ Detector        │ │ Validator        │   │
│  │ (antibot_config.py)│ │(compute_accel.  │ │ (NEW)            │   │
│  │                    │ │ erator.py)      │ │                  │   │
│  └────────┬───────────┘ └────────┬────────┘ └──────────────────┘   │
│           │                      │                                  │
│           │ load_preset()        │ detect_device()                  │
│           ▼                      ▼                                  │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  Antibot Orchestrator                                        │   │
│  │  (antibot_orchestrator.py)                                   │   │
│  │  • Receives antibot_preset configuration                     │   │
│  │  • Receives hardware detection results                       │   │
│  │  • Configures 5 antibot layers                               │   │
│  └──────────────────┬───────────────────────────────────────────┘   │
│                     │                                                │
│                     ▼                                                │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  CAPTCHA Solver (captcha_solver.py)                          │   │
│  │  • Uses GPU when available (NVIDIA/AMD/Apple/Intel)          │   │
│  │  • Falls back to CPU when GPU unavailable                    │   │
│  │  • PaddleOCR/EasyOCR with GPU acceleration                   │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```


### Component Interaction Flow

#### 1. Application Startup Flow

```
Backend Startup
├─> Hardware Detector initializes (< 2s timeout)
│   ├─> Check torch.cuda.is_available() (NVIDIA)
│   ├─> Check torch.version.hip (AMD)
│   ├─> Check torch.backends.mps.is_available() (Apple)
│   ├─> Check openvino.runtime (Intel)
│   ├─> Check TPU_NAME env var (TPU)
│   └─> Store detected device type in runtime state
│
├─> Configuration Manager loads presets
│   ├─> Load "high-stealth", "balanced", "high-speed" presets
│   └─> Store in memory for fast access
│
└─> Antibot Orchestrator initializes with default preset
    └─> Ready to receive job requests

Frontend Loads
├─> GET /api/modes/available
│   └─> Receives mode list, preset list, compatibility matrix
│
├─> GET /api/hardware/status
│   └─> Receives device_type, capabilities, acceleration flags
│
└─> Display mode selection dropdowns + hardware status badge
```

#### 2. Job Submission Flow

```
User Interaction
├─> User selects: mode="deep", preset="balanced"
├─> Frontend validates combination (client-side check)
└─> POST /api/jobs {query, mode, antibot_preset: "balanced", ...}

Backend Processing
├─> Parse ScrapeStartRequest (Pydantic validation)
│
├─> Mode Validator checks compatibility
│   ├─> IF mode="fast" AND preset="high-stealth" → REJECT (400 error)
│   ├─> IF mode="deep" AND preset="high-speed" → REJECT (400 error)
│   └─> ELSE → ACCEPT
│
├─> Configuration Manager loads preset configuration
│   └─> load_preset("balanced") → AntiBotConfiguration
│
├─> Create job-specific Orchestrator instance
│   ├─> Apply preset configuration to 5 layers
│   ├─> Query Hardware Detector for device type
│   └─> Pass device info to CAPTCHA Solver
│
└─> Execute scraping job with configured layers
```


#### 3. CAPTCHA Solving with GPU Acceleration

```
CAPTCHA Detected
├─> CAPTCHA Solver detect_captcha(page)
│   └─> Returns CAPTCHAChallenge(type=recaptcha_v2)
│
├─> solve_captcha(page, challenge)
│   ├─> Query Hardware Detector: device_type="nvidia_gpu"
│   │
│   ├─> IF device_type contains "gpu":
│   │   ├─> PaddleOCR(use_gpu=True) OR
│   │   └─> EasyOCR(gpu=True)
│   │
│   └─> ELSE (device_type="cpu"):
│       └─> PaddleOCR(use_gpu=False) OR EasyOCR(gpu=False)
│
└─> Return solved CAPTCHA token
```

## Components and Interfaces

### Frontend Components

#### 1. Mode Selection Component (NEW)

**Location**: `/frontend/app/page.tsx` (inline component, lines ~600-750)

**Purpose**: Display dropdown controls for mode and preset selection

**State Management**:
```typescript
interface ModeSelectionState {
  selectedMode: string;              // Current scraping mode
  selectedPreset: string;            // Current antibot preset
  availableModes: ModeOption[];      // Fetched from backend
  availablePresets: PresetOption[];  // Fetched from backend
  compatibilityMatrix: Record<string, string[]>; // Valid combinations
  loading: boolean;
}

interface ModeOption {
  value: string;           // "fast", "balanced", "deep"
  label: string;           // "Quick Scan", "Balanced Scan"
  description: string;     // Tooltip text
}

interface PresetOption {
  value: string;           // "high-stealth", "balanced", "high-speed"
  label: string;           // "Maximum Stealth (0% Detection)"
  description: string;     // Tooltip text
  speedImpact: "fast" | "moderate" | "slow";
}
```

**Behavior**:
- On mount: Fetch `/api/modes/available`, populate dropdowns
- On mode change: Filter available presets based on compatibility matrix
- On preset change: Update performance indicator
- On form submit: Include both `mode` and `antibot_preset` in request payload


#### 2. Hardware Status Indicator (NEW)

**Location**: `/frontend/app/page.tsx` (inline component, near existing status strip)

**Purpose**: Display detected hardware accelerator status

**State Management**:
```typescript
interface HardwareStatus {
  device_type: "nvidia_gpu" | "amd_gpu" | "apple_gpu" | "intel_gpu" | "tpu" | "cpu";
  capabilities: {
    ocr_acceleration: boolean;
    embedding_acceleration: boolean;
  };
  displayText: string; // "Using NVIDIA GPU for acceleration"
}
```

**Behavior**:
- On mount: Fetch `/api/hardware/status`
- Display badge with color coding:
  - Green (GPU detected): "Using [GPU Type] for acceleration"
  - Gray (CPU only): "Using CPU (No GPU detected)"
- Update on hardware change (hot-plug detection not required for MVP)

#### 3. Performance Indicator (NEW)

**Location**: `/frontend/app/page.tsx` (inline component, near mode selection)

**Purpose**: Show expected performance impact of selected mode + preset combination

**State Management**:
```typescript
interface PerformanceImpact {
  speedLabel: string;    // "Very Fast", "Moderate", "Slow"
  stealthLabel: string;  // "Maximum", "Moderate", "Minimal"
  colorTone: "green" | "yellow" | "red";
  combinedEstimate: string; // "Fast with Moderate Stealth"
}
```

**Calculation Logic**:
```typescript
function calculatePerformance(mode: string, preset: string): PerformanceImpact {
  const speedMap = {
    fast: { label: "Very Fast", tone: "green" },
    balanced: { label: "Moderate", tone: "yellow" },
    deep: { label: "Slow (Thorough)", tone: "red" },
  };
  
  const stealthMap = {
    "high-stealth": { label: "Maximum (Slowest)", tone: "red" },
    "balanced": { label: "Moderate", tone: "yellow" },
    "high-speed": { label: "Minimal (Fastest)", tone: "green" },
  };
  
  // Combine worst-case tone
  const tone = speedMap[mode].tone === "red" || stealthMap[preset].tone === "red" 
    ? "red" : "yellow";
  
  return {
    speedLabel: speedMap[mode].label,
    stealthLabel: stealthMap[preset].label,
    colorTone: tone,
    combinedEstimate: `${speedMap[mode].label} with ${stealthMap[preset].label} Stealth`
  };
}
```


### Backend Components

#### 1. Hardware Detector (ENHANCED)

**Location**: `/backend/asagus/layers/compute_accelerator.py`

**Current State**: Skeleton implementation exists with `_detect_device()` method

**Enhancement Strategy**:
- Add timeout mechanism (2-second limit)
- Add error handling for missing libraries
- Add logging for each detection attempt
- Store detection result in module-level variable for fast access

**Implementation**:
```python
class HardwareDetector:
    """Singleton hardware detection with caching and timeout."""
    
    _instance = None
    _detection_result: str = "cpu"
    _detection_timestamp: float = 0.0
    _detection_timeout_seconds: float = 2.0
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def detect_with_timeout(self) -> str:
        """Detect hardware with timeout protection."""
        import time
        start_time = time.time()
        
        try:
            # Try NVIDIA GPU first (most common)
            if self._check_nvidia_gpu(start_time):
                return "nvidia_gpu"
            
            # Try AMD GPU (ROCm)
            if self._check_amd_gpu(start_time):
                return "amd_gpu"
            
            # Try Apple Silicon (Metal)
            if self._check_apple_gpu(start_time):
                return "apple_gpu"
            
            # Try Intel GPU (OpenVINO)
            if self._check_intel_gpu(start_time):
                return "intel_gpu"
            
            # Try TPU
            if self._check_tpu(start_time):
                return "tpu"
            
        except Exception as e:
            logger.warning(f"Hardware detection error: {e}")
        
        return "cpu"
    
    def _check_nvidia_gpu(self, start_time: float) -> bool:
        """Check for NVIDIA GPU with timeout."""
        if time.time() - start_time > self._detection_timeout_seconds:
            return False
        
        try:
            import torch
            is_available = torch.cuda.is_available()
            logger.info(f"NVIDIA GPU detection: {is_available}")
            return is_available
        except ImportError:
            logger.debug("torch not installed, skipping NVIDIA detection")
            return False
        except Exception as e:
            logger.warning(f"NVIDIA detection error: {e}")
            return False
```

**Initialization Point**: Application startup in `main.py` before route registration

```python
# In main.py, after imports
from asagus.layers.compute_accelerator import HardwareDetector

# Global instance
hardware_detector = HardwareDetector()

def create_app() -> FastAPI:
    settings = get_settings()
    
    # Initialize hardware detection at startup
    detected_device = hardware_detector.detect_with_timeout()
    logger.info(f"Hardware detection complete: {detected_device}")
    
    # Store in runtime for fast access
    runtime.hardware_device = detected_device
    
    app = FastAPI(...)
    # ... rest of setup
```


#### 2. Mode Validator (NEW)

**Location**: `/backend/asagus/layers/mode_validator.py` (new file)

**Purpose**: Validate mode-preset combinations and enforce compatibility rules

**Implementation**:
```python
from typing import Literal
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

ScrapingMode = Literal[
    "fast", "balanced", "deep", "deep_agent", 
    "parallel", "research", "focused", "comprehensive", "adaptive"
]

AntibotPreset = Literal["high-stealth", "balanced", "high-speed"]

@dataclass
class ValidationResult:
    """Result of mode-preset validation."""
    valid: bool
    reason: str = ""

class ModeValidator:
    """Validates mode-preset combinations for compatibility."""
    
    # Incompatible combinations
    INCOMPATIBLE_COMBINATIONS = {
        ("fast", "high-stealth"): "Fast mode conflicts with high-stealth preset (requires maximum speed)",
        ("deep", "high-speed"): "Deep mode conflicts with high-speed preset (requires thorough analysis)",
    }
    
    def validate_combination(
        self, 
        mode: ScrapingMode, 
        preset: AntibotPreset
    ) -> ValidationResult:
        """
        Validate that mode and preset are compatible.
        
        Args:
            mode: Scraping depth mode
            preset: Antibot stealth preset
        
        Returns:
            ValidationResult indicating validity and reason if invalid
        """
        combination_key = (mode, preset)
        
        if combination_key in self.INCOMPATIBLE_COMBINATIONS:
            reason = self.INCOMPATIBLE_COMBINATIONS[combination_key]
            logger.warning(f"Invalid combination: {mode} + {preset} - {reason}")
            return ValidationResult(valid=False, reason=reason)
        
        logger.info(f"Valid combination: {mode} + {preset}")
        return ValidationResult(valid=True)
    
    def get_compatibility_matrix(self) -> dict[str, list[str]]:
        """
        Get compatibility matrix for frontend.
        
        Returns:
            Dictionary mapping modes to compatible presets
        """
        all_modes: list[ScrapingMode] = [
            "fast", "balanced", "deep", "deep_agent", 
            "parallel", "research", "focused", "comprehensive", "adaptive"
        ]
        all_presets: list[AntibotPreset] = ["high-stealth", "balanced", "high-speed"]
        
        compatibility = {}
        for mode in all_modes:
            compatible_presets = []
            for preset in all_presets:
                if self.validate_combination(mode, preset).valid:
                    compatible_presets.append(preset)
            compatibility[mode] = compatible_presets
        
        return compatibility

# Singleton instance
_validator = ModeValidator()

def get_mode_validator() -> ModeValidator:
    """Get global mode validator instance."""
    return _validator
```


#### 3. Configuration Manager Integration

**Location**: `/backend/asagus/layers/antibot_config.py` (existing file)

**Enhancement Strategy**: No changes required - existing implementation already supports:
- Preset loading via `load_preset(preset_name)`
- Three presets: "high-stealth", "balanced", "high-speed"
- Per-job configuration isolation

**Usage Pattern**:
```python
# In job execution (main.py)
config_manager = ConfigurationManager()
config_manager.load_preset(job.request.antibot_preset)
antibot_config = config_manager.get_config()

# Create job-specific orchestrator
orchestrator = AntiBotOrchestrator(
    config=AntiBotConfig(
        framework_priority=antibot_config.global_config.framework_priority,
        stealth_approach=StealthApproach[antibot_config.global_config.stealth_approach],
        tls_fingerprint=BrowserTLSFingerprint[antibot_config.global_config.tls_fingerprint],
        device_profile_name=antibot_config.global_config.device_profile,
        enable_behavioral_simulation=antibot_config.global_config.enable_behavioral,
    ),
    config_manager=config_manager
)
```

#### 4. CAPTCHA Solver Integration

**Location**: `/backend/asagus/layers/captcha_solver.py` (existing file)

**Enhancement Strategy**: Modify to accept hardware detector instance

**Modified Constructor**:
```python
class CAPTCHASolver:
    def __init__(
        self, 
        use_yolov8: bool = False, 
        use_ml_models: bool = False,
        hardware_detector: HardwareDetector | None = None
    ):
        self.logger = logging.getLogger(__name__)
        self.use_yolov8 = use_yolov8
        self.use_ml_models = use_ml_models
        self.hardware_detector = hardware_detector
        
        # Determine if GPU is available
        self.device_type = "cpu"
        if hardware_detector:
            self.device_type = hardware_detector._detection_result
        
        self.logger.info(f"CAPTCHA Solver initialized with device: {self.device_type}")
```

**Modified Solving Methods**:
```python
async def _solve_with_paddleocr(self, image_path: str) -> str:
    """Use PaddleOCR with GPU if available."""
    try:
        from paddleocr import PaddleOCR
        
        # Enable GPU for all GPU types
        use_gpu = "gpu" in self.device_type or self.device_type == "tpu"
        
        self.logger.info(f"PaddleOCR GPU mode: {use_gpu} (device: {self.device_type})")
        ocr = PaddleOCR(use_gpu=use_gpu, lang="en")
        result = ocr.ocr(image_path)
        return " ".join([line[0][1] for line in result[0]]) if result else ""
    except ImportError:
        self.logger.warning("PaddleOCR not installed")
        return ""
    except Exception as e:
        self.logger.error(f"PaddleOCR error: {e}")
        return ""
```


## Data Models

### Backend Request/Response Models

#### 1. ScrapeStartRequest (EXTENDED)

**Location**: `/backend/asagus/models.py`

**Modification**: Add `antibot_preset` field

```python
from pydantic import BaseModel, Field
from typing import Literal

class ScrapeStartRequest(BaseModel):
    """Request model for starting a scrape job."""
    
    # Existing fields (unchanged)
    query: str
    location: str = ""
    limit: int = 100
    max_pages: int = 0
    mode: Literal[
        "fast", "balanced", "deep", "deep_agent", 
        "parallel", "research", "focused", "comprehensive", "adaptive"
    ] = "balanced"
    
    # NEW FIELD
    antibot_preset: Literal["high-stealth", "balanced", "high-speed"] = Field(
        default="balanced",
        description="Antibot stealth configuration preset"
    )
    
    # ... rest of existing fields (unchanged)
    discovery_mode: str = "website_first"
    lead_target: str = "businesses"
    proxy_strategy: str = "auto"
    # ... (50+ other fields remain unchanged)
```

#### 2. ModesAvailableResponse (NEW)

**Location**: `/backend/asagus/models.py`

```python
from pydantic import BaseModel
from typing import List, Dict

class ModeOption(BaseModel):
    """Scraping mode option."""
    value: str
    label: str
    description: str

class PresetOption(BaseModel):
    """Antibot preset option."""
    value: str
    label: str
    description: str
    speed_impact: Literal["fast", "moderate", "slow"]

class ModesAvailableResponse(BaseModel):
    """Response for /api/modes/available endpoint."""
    modes: List[ModeOption]
    presets: List[PresetOption]
    compatibility_matrix: Dict[str, List[str]]
```

#### 3. HardwareStatusResponse (NEW)

**Location**: `/backend/asagus/models.py`

```python
from pydantic import BaseModel

class HardwareStatusResponse(BaseModel):
    """Response for /api/hardware/status endpoint."""
    device_type: Literal[
        "nvidia_gpu", "amd_gpu", "apple_gpu", 
        "intel_gpu", "tpu", "cpu"
    ]
    capabilities: Dict[str, bool]  # ocr_acceleration, embedding_acceleration
    ocr_acceleration: bool
    embedding_acceleration: bool
```


### Frontend Data Models

#### TypeScript Interface Definitions

**Location**: `/frontend/lib/api.ts`

```typescript
// Extended job request interface
export interface ScrapeStartRequest {
  query: string;
  location: string;
  limit: number;
  max_pages: number;
  mode: string;
  antibot_preset?: "high-stealth" | "balanced" | "high-speed"; // NEW FIELD
  discovery_mode: string;
  lead_target: string;
  // ... all existing fields
}

// NEW: Modes API response
export interface ModeOption {
  value: string;
  label: string;
  description: string;
}

export interface PresetOption {
  value: string;
  label: string;
  description: string;
  speed_impact: "fast" | "moderate" | "slow";
}

export interface ModesAvailableResponse {
  modes: ModeOption[];
  presets: PresetOption[];
  compatibility_matrix: Record<string, string[]>;
}

// NEW: Hardware status response
export interface HardwareStatusResponse {
  device_type: "nvidia_gpu" | "amd_gpu" | "apple_gpu" | "intel_gpu" | "tpu" | "cpu";
  capabilities: {
    ocr_acceleration: boolean;
    embedding_acceleration: boolean;
  };
  ocr_acceleration: boolean;
  embedding_acceleration: boolean;
}
```

## API Contracts

### 1. GET /api/modes/available

**Purpose**: Return available scraping modes, antibot presets, and compatibility matrix

**Request**: None

**Response** (200 OK):
```json
{
  "modes": [
    {
      "value": "fast",
      "label": "Quick Scan",
      "description": "Fast scraping with minimal overhead. Best for quick results."
    },
    {
      "value": "balanced",
      "label": "Balanced Scan",
      "description": "Default mix of speed and completeness. Recommended for most use cases."
    },
    {
      "value": "deep",
      "label": "Deep Scan",
      "description": "Maximum thoroughness with all checks enabled. Slower but most comprehensive."
    }
  ],
  "presets": [
    {
      "value": "high-stealth",
      "label": "Maximum Stealth (0% Detection)",
      "description": "Uses Camoufox binary patches for 0% detection rate. Slowest but most reliable.",
      "speed_impact": "slow"
    },
    {
      "value": "balanced",
      "label": "Balanced Protection (67% Pass Rate)",
      "description": "Uses Patchright with 67% pass rate. Good balance of speed and stealth.",
      "speed_impact": "moderate"
    },
    {
      "value": "high-speed",
      "label": "Fast & Lightweight",
      "description": "Uses JS-shim for minimal overhead. Fast but lower success rate against strong antibot.",
      "speed_impact": "fast"
    }
  ],
  "compatibility_matrix": {
    "fast": ["balanced", "high-speed"],
    "balanced": ["high-stealth", "balanced", "high-speed"],
    "deep": ["high-stealth", "balanced"]
  }
}
```

**Performance Target**: < 100ms response time


### 2. GET /api/hardware/status

**Purpose**: Return detected hardware accelerator status and capabilities

**Request**: None

**Response** (200 OK):
```json
{
  "device_type": "nvidia_gpu",
  "capabilities": {
    "ocr_acceleration": true,
    "embedding_acceleration": true
  },
  "ocr_acceleration": true,
  "embedding_acceleration": true
}
```

**Response** (200 OK - CPU only):
```json
{
  "device_type": "cpu",
  "capabilities": {
    "ocr_acceleration": false,
    "embedding_acceleration": false
  },
  "ocr_acceleration": false,
  "embedding_acceleration": false
}
```

**Performance Target**: < 50ms response time (read from cached detection result)

### 3. POST /api/jobs (EXTENDED)

**Purpose**: Start a new scrape job with mode and preset configuration

**Request Body** (extended):
```json
{
  "query": "restaurants in Seattle",
  "location": "Seattle, WA",
  "limit": 100,
  "mode": "deep",
  "antibot_preset": "balanced",  // NEW FIELD
  "discovery_mode": "website_first",
  "enable_network_fetch": true,
  "enable_search_discovery": true
  // ... all other existing fields
}
```

**Response** (200 OK): Returns `ScrapeJob` object (unchanged structure)

**Response** (400 Bad Request - Invalid Combination):
```json
{
  "detail": "Mode 'fast' is incompatible with preset 'high-stealth'. Fast mode requires maximum speed, which conflicts with stealth overhead."
}
```

**Response** (400 Bad Request - Invalid Preset):
```json
{
  "detail": "Invalid antibot_preset value. Must be one of: high-stealth, balanced, high-speed"
}
```

**Validation Logic**:
1. Pydantic validates `antibot_preset` is one of the three valid values
2. Mode Validator checks combination compatibility
3. If valid: Proceed with job creation
4. If invalid: Return 400 error with descriptive message


## Algorithms

### 1. GPU Detection Algorithm

**Purpose**: Detect available hardware accelerators within 2-second timeout

**Pseudocode**:
```
function detect_hardware_with_timeout(timeout_seconds=2.0):
    start_time = current_time()
    detected_device = "cpu"
    
    // Check NVIDIA GPU (most common)
    if elapsed_time(start_time) < timeout_seconds:
        try:
            import torch
            if torch.cuda.is_available():
                log_info("NVIDIA GPU detected")
                return "nvidia_gpu"
        catch ImportError:
            log_debug("torch not installed")
        catch Exception as e:
            log_warning("NVIDIA detection failed: " + e)
    
    // Check AMD GPU (ROCm)
    if elapsed_time(start_time) < timeout_seconds:
        try:
            import torch
            if torch.version.hip is not None:
                log_info("AMD GPU detected")
                return "amd_gpu"
        catch (ImportError, AttributeError):
            log_debug("AMD GPU not available")
    
    // Check Apple Silicon (Metal)
    if elapsed_time(start_time) < timeout_seconds:
        try:
            import platform, torch
            if platform.system() == "Darwin":
                if torch.backends.mps.is_available():
                    log_info("Apple Silicon GPU detected")
                    return "apple_gpu"
        catch ImportError:
            log_debug("Apple GPU check skipped")
    
    // Check Intel GPU (OpenVINO)
    if elapsed_time(start_time) < timeout_seconds:
        try:
            from openvino.runtime import Core
            core = Core()
            devices = core.available_devices
            if any("GPU" in device for device in devices):
                log_info("Intel GPU detected")
                return "intel_gpu"
        catch ImportError:
            log_debug("OpenVINO not installed")
    
    // Check TPU
    if elapsed_time(start_time) < timeout_seconds:
        if "TPU_NAME" in environment or "COLAB_TPU_ADDR" in environment:
            log_info("TPU detected")
            return "tpu"
    
    log_info("No GPU detected, using CPU")
    return "cpu"
```

**Timeout Strategy**:
- Hard timeout at 2 seconds
- Check elapsed time before each detection attempt
- If timeout exceeded, skip remaining checks and return current result
- Never block startup beyond 2 seconds

**Error Handling**:
- Catch `ImportError` for missing libraries → Skip that check
- Catch all other exceptions → Log warning, continue to next check
- Never propagate exceptions that would crash startup


### 2. Mode-Preset Validation Algorithm

**Purpose**: Validate mode-preset combinations before job execution

**Pseudocode**:
```
// Incompatibility rules
INCOMPATIBLE = {
    ("fast", "high-stealth"): "Fast mode requires maximum speed; high-stealth adds overhead",
    ("deep", "high-speed"): "Deep mode requires thorough analysis; high-speed skips checks"
}

function validate_combination(mode, preset):
    key = (mode, preset)
    
    if key in INCOMPATIBLE:
        reason = INCOMPATIBLE[key]
        log_warning(f"Invalid combination: {mode} + {preset}")
        return ValidationResult(valid=false, reason=reason)
    
    log_info(f"Valid combination: {mode} + {preset}")
    return ValidationResult(valid=true, reason="")

function get_compatibility_matrix():
    all_modes = ["fast", "balanced", "deep", "deep_agent", "parallel", 
                 "research", "focused", "comprehensive", "adaptive"]
    all_presets = ["high-stealth", "balanced", "high-speed"]
    
    matrix = {}
    for mode in all_modes:
        compatible = []
        for preset in all_presets:
            if validate_combination(mode, preset).valid:
                compatible.append(preset)
        matrix[mode] = compatible
    
    return matrix
```

**Validation Flow in Request Handler**:
```
async function handle_job_request(request):
    // 1. Pydantic validates field types
    mode = request.mode
    preset = request.antibot_preset  // defaults to "balanced" if omitted
    
    // 2. Mode validator checks compatibility
    validator = ModeValidator()
    result = validator.validate_combination(mode, preset)
    
    if not result.valid:
        return HTTPException(
            status_code=400,
            detail=f"Mode '{mode}' is incompatible with preset '{preset}'. {result.reason}"
        )
    
    // 3. Proceed with job creation
    config_manager.load_preset(preset)
    // ... create job
```

### 3. Configuration Flow Algorithm

**Purpose**: Apply preset configuration to antibot orchestrator for each job

**Pseudocode**:
```
function configure_orchestrator_for_job(job_request, hardware_device):
    // 1. Load preset configuration
    config_manager = ConfigurationManager()
    config_manager.load_preset(job_request.antibot_preset)
    preset_config = config_manager.get_config()
    
    // 2. Create orchestrator configuration from preset
    orchestrator_config = AntiBotConfig(
        framework_priority = preset_config.global_config.framework_priority,
        stealth_approach = preset_config.global_config.stealth_approach,
        tls_fingerprint = preset_config.global_config.tls_fingerprint,
        device_profile_name = preset_config.global_config.device_profile,
        enable_behavioral_simulation = preset_config.global_config.enable_behavioral
    )
    
    // 3. Create job-specific orchestrator instance
    orchestrator = AntiBotOrchestrator(
        config = orchestrator_config,
        proxy_urls = preset_config.proxy_config.pool,
        config_manager = config_manager
    )
    
    // 4. Initialize CAPTCHA solver with hardware info
    captcha_solver = CAPTCHASolver(
        use_yolov8 = false,
        use_ml_models = false,
        hardware_detector = hardware_device
    )
    
    // 5. Attach solver to orchestrator
    orchestrator.captcha_solver = captcha_solver
    
    return orchestrator
```

**Key Points**:
- Each job gets its own orchestrator instance (isolation)
- Preset configuration is loaded fresh per job
- Hardware detection result is shared (global state)
- No modification of global configuration state


## Error Handling

### 1. GPU Detection Failures

**Scenario**: GPU libraries not installed or detection fails

**Strategy**: Graceful degradation to CPU

**Implementation**:
```python
def _check_nvidia_gpu(self, start_time: float) -> bool:
    """Check for NVIDIA GPU with timeout."""
    try:
        import torch
        return torch.cuda.is_available()
    except ImportError:
        logger.debug("torch not installed, skipping NVIDIA GPU detection")
        return False
    except Exception as e:
        logger.warning(f"NVIDIA GPU detection error: {e}")
        return False
```

**Error Recovery**:
- Log error (warning level)
- Continue with next detection method
- Return "cpu" if all checks fail
- System remains fully operational

### 2. Invalid Mode-Preset Combination

**Scenario**: User submits incompatible mode + preset

**Strategy**: Return 400 error with clear explanation

**Implementation**:
```python
@app.post("/api/jobs")
async def start_job(payload: ScrapeStartRequest, ...):
    validator = ModeValidator()
    result = validator.validate_combination(
        payload.mode, 
        payload.antibot_preset
    )
    
    if not result.valid:
        raise HTTPException(
            status_code=400,
            detail=f"Mode '{payload.mode}' is incompatible with preset "
                   f"'{payload.antibot_preset}'. {result.reason}"
        )
    
    # Continue with job creation
```

**Frontend Handling**:
- Display error message to user
- Suggest compatible alternatives
- Keep form state intact for correction

### 3. Hardware Status API Timeout

**Scenario**: Hardware detection takes longer than expected

**Strategy**: Return cached result or "cpu" default

**Implementation**:
```python
@app.get("/api/hardware/status")
async def hardware_status():
    try:
        # Return cached detection result (fast)
        device_type = runtime.hardware_device or "cpu"
        
        return HardwareStatusResponse(
            device_type=device_type,
            capabilities={
                "ocr_acceleration": "gpu" in device_type or device_type == "tpu",
                "embedding_acceleration": "gpu" in device_type or device_type == "tpu"
            },
            ocr_acceleration="gpu" in device_type or device_type == "tpu",
            embedding_acceleration="gpu" in device_type or device_type == "tpu"
        )
    except Exception as e:
        logger.error(f"Hardware status error: {e}")
        # Return safe default
        return HardwareStatusResponse(
            device_type="cpu",
            capabilities={"ocr_acceleration": False, "embedding_acceleration": False},
            ocr_acceleration=False,
            embedding_acceleration=False
        )
```


### 4. CAPTCHA Solver GPU Initialization Failure

**Scenario**: GPU detected but OCR library fails to use it

**Strategy**: Fall back to CPU mode for that specific solve attempt

**Implementation**:
```python
async def _solve_with_paddleocr(self, image_path: str) -> str:
    """Use PaddleOCR with GPU if available."""
    try:
        from paddleocr import PaddleOCR
        
        use_gpu = "gpu" in self.device_type or self.device_type == "tpu"
        
        try:
            ocr = PaddleOCR(use_gpu=use_gpu, lang="en")
            result = ocr.ocr(image_path)
            return self._extract_text(result)
        except Exception as gpu_error:
            # GPU initialization failed, try CPU fallback
            logger.warning(f"GPU OCR failed: {gpu_error}, falling back to CPU")
            ocr = PaddleOCR(use_gpu=False, lang="en")
            result = ocr.ocr(image_path)
            return self._extract_text(result)
            
    except ImportError:
        logger.warning("PaddleOCR not installed")
        return ""
    except Exception as e:
        logger.error(f"PaddleOCR error: {e}")
        return ""
```

### 5. Configuration Preset Not Found

**Scenario**: Invalid preset name provided

**Strategy**: Pydantic validation rejects at request level

**Implementation**:
```python
# In Pydantic model
class ScrapeStartRequest(BaseModel):
    antibot_preset: Literal["high-stealth", "balanced", "high-speed"] = "balanced"
```

**Pydantic Response** (422 Unprocessable Entity):
```json
{
  "detail": [
    {
      "loc": ["body", "antibot_preset"],
      "msg": "value is not a valid enumeration member; permitted: 'high-stealth', 'balanced', 'high-speed'",
      "type": "type_error.enum"
    }
  ]
}
```

### 6. Frontend API Fetch Failures

**Scenario**: Backend unavailable or network error

**Strategy**: Display cached/default values with error indicator

**Implementation**:
```typescript
async function loadModesAvailable(): Promise<ModesAvailableResponse | null> {
  try {
    const response = await fetch("/api/modes/available");
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const data = await response.json();
    return data;
  } catch (error) {
    console.error("Failed to load modes:", error);
    
    // Return default fallback
    return {
      modes: [
        { value: "balanced", label: "Balanced Scan", description: "Default mode" }
      ],
      presets: [
        { value: "balanced", label: "Balanced Protection", description: "Default preset", speed_impact: "moderate" }
      ],
      compatibility_matrix: { "balanced": ["balanced"] }
    };
  }
}
```


## Testing Strategy

### Unit Tests

**Backend Unit Tests**:

1. **Hardware Detection Tests** (`test_hardware_detector.py`)
   - Test NVIDIA GPU detection with mock torch
   - Test AMD GPU detection with mock torch.version.hip
   - Test Apple Silicon detection with mock platform + torch
   - Test Intel GPU detection with mock openvino
   - Test TPU detection with mock environment variables
   - Test timeout enforcement (mock slow detection)
   - Test graceful degradation on ImportError
   - Test exception handling for each detection method

2. **Mode Validator Tests** (`test_mode_validator.py`)
   - Test valid combinations return ValidationResult(valid=True)
   - Test fast + high-stealth returns ValidationResult(valid=False)
   - Test deep + high-speed returns ValidationResult(valid=False)
   - Test compatibility matrix generation
   - Test all 9 modes × 3 presets = 27 combinations

3. **API Endpoint Tests** (`test_main_api.py`)
   - Test GET /api/modes/available returns correct structure
   - Test GET /api/hardware/status returns correct structure
   - Test POST /api/jobs accepts antibot_preset field
   - Test POST /api/jobs rejects invalid combinations (400)
   - Test POST /api/jobs defaults to "balanced" when omitted
   - Test backwards compatibility (jobs without preset still work)

4. **CAPTCHA Solver Tests** (`test_captcha_solver_gpu.py`)
   - Test GPU mode enabled when hardware_detector reports GPU
   - Test CPU fallback when GPU initialization fails
   - Test PaddleOCR called with use_gpu=True when GPU available
   - Test EasyOCR called with gpu=True when GPU available

**Frontend Unit Tests** (Jest + React Testing Library):

1. **Mode Selection Component Tests**
   - Test dropdowns render with fetched options
   - Test incompatible presets are disabled based on selected mode
   - Test form submission includes both mode and preset
   - Test localStorage persistence of selections
   - Test loading state while fetching modes API

2. **Hardware Status Indicator Tests**
   - Test displays "Using NVIDIA GPU" when device_type="nvidia_gpu"
   - Test displays "Using CPU" when device_type="cpu"
   - Test fetches hardware status on mount
   - Test error handling when API fails

3. **Performance Indicator Tests**
   - Test calculates correct combined impact
   - Test color coding (green/yellow/red)
   - Test updates when mode or preset changes


### Integration Tests

1. **End-to-End Job Flow**
   - Create job with mode="deep" + preset="balanced"
   - Verify Configuration Manager loads "balanced" preset
   - Verify Orchestrator receives correct configuration
   - Verify CAPTCHA solver gets hardware detector instance
   - Verify job executes successfully

2. **Hardware Acceleration Integration**
   - Mock NVIDIA GPU detection
   - Create job with CAPTCHA challenges
   - Verify PaddleOCR called with use_gpu=True
   - Verify CAPTCHA solved successfully

3. **Mode Validation Integration**
   - Submit job with mode="fast" + preset="high-stealth"
   - Verify 400 error returned
   - Verify error message contains "incompatible"
   - Verify job not created in database

4. **Frontend-Backend Integration**
   - Frontend fetches /api/modes/available
   - Frontend displays mode dropdowns
   - User selects mode + preset
   - Frontend submits job
   - Verify job created with correct preset
   - Verify hardware status displayed correctly

### Manual Testing Checklist

**Hardware Detection**:
- [ ] Test on system with NVIDIA GPU (should detect "nvidia_gpu")
- [ ] Test on system with AMD GPU (should detect "amd_gpu")
- [ ] Test on Mac with Apple Silicon (should detect "apple_gpu")
- [ ] Test on system without GPU (should detect "cpu")
- [ ] Test startup time (should complete in < 2 seconds)

**Mode Selection UI**:
- [ ] Verify dropdown shows 9 modes with user-friendly labels
- [ ] Verify dropdown shows 3 presets with descriptions
- [ ] Verify tooltips appear on hover
- [ ] Verify incompatible presets disabled based on selected mode
- [ ] Verify localStorage persistence across page reloads

**Hardware Status Display**:
- [ ] Verify badge shows correct GPU type
- [ ] Verify badge shows "Using CPU" when no GPU
- [ ] Verify badge color coding (green for GPU, gray for CPU)

**Performance Indicator**:
- [ ] Verify shows "Very Fast" for mode="fast"
- [ ] Verify shows "Slow (Thorough)" for mode="deep"
- [ ] Verify shows combined estimate
- [ ] Verify color changes based on selection

**Job Execution**:
- [ ] Submit job with preset="high-stealth"
- [ ] Verify Camoufox stealth approach applied
- [ ] Verify job completes successfully
- [ ] Submit job with preset="high-speed"
- [ ] Verify JS-shim approach applied
- [ ] Verify faster execution time

**Error Handling**:
- [ ] Try to submit fast + high-stealth (should show error)
- [ ] Try to submit deep + high-speed (should show error)
- [ ] Disconnect backend, verify frontend shows fallback
- [ ] Test with missing GPU libraries (should fall back to CPU)

