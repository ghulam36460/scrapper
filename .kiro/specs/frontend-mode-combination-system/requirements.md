# Requirements Document

## Introduction

The Frontend Mode Combination System enables non-technical users to easily configure and combine scraping depth modes with antibot protection levels through an intuitive user interface. The system automatically detects available hardware accelerators (GPU/TPU/DPU) and leverages them to enhance scraping performance, CAPTCHA solving, and antibot layer processing. This feature extends the existing ASAGUS Scraper v3 architecture without removing any existing functionality.

The system addresses three core needs:
1. **Simplified Mode Selection**: Non-technical users can select scraping modes (fast, balanced, deep, etc.) and antibot stealth levels (high-stealth, balanced, high-speed) simultaneously through dropdown controls
2. **Automatic Hardware Acceleration**: The system detects NVIDIA GPU, AMD GPU, Apple Silicon, Intel GPU, and TPU resources and automatically accelerates CAPTCHA solving, ML model inference, and scraping operations
3. **Real-Time Feedback**: Users receive clear indicators showing active modes, detected hardware, and expected performance impact

## Glossary

- **Frontend_UI**: The Next.js-based user interface component in page.tsx that displays scraping configuration controls
- **Mode_Selection_Component**: React component that allows users to select scraping depth mode and antibot preset simultaneously
- **Backend_API**: FastAPI backend that processes scrape job requests and coordinates all layers
- **Scraping_Mode**: Depth mode controlling thoroughness of data collection (fast, balanced, deep, deep_agent, parallel, research, focused, comprehensive, adaptive)
- **Antibot_Preset**: Stealth configuration preset (high-stealth, balanced, high-speed) controlling protection level
- **Compute_Accelerator**: Python module that detects and manages GPU/TPU/DPU hardware resources
- **Orchestrator**: Backend component coordinating all antibot layers and scraping operations
- **CAPTCHA_Solver**: Component that processes CAPTCHA challenges using OCR models
- **ScrapeStartRequest**: Pydantic model defining the structure of scrape job requests
- **Hardware_Detector**: Component that identifies available GPU/TPU/DPU at system startup
- **Mode_Validator**: Backend service that validates mode-preset combinations for compatibility
- **Performance_Indicator**: UI element showing expected performance impact of selected configuration
- **Configuration_Manager**: Backend component managing antibot configuration presets
- **GPU_Device**: Graphics processing unit for accelerating computation (NVIDIA, AMD, Apple Silicon, Intel)
- **TPU_Device**: Tensor processing unit specialized for ML workloads
- **Mode_API_Endpoint**: REST endpoint at /api/modes/available returning compatible mode combinations

## Requirements

### Requirement 1: Frontend Mode Selection Interface

**User Story:** As a non-technical user, I want to select both scraping depth mode and antibot stealth level from dropdown menus, so that I can configure scraping jobs without understanding technical details.

#### Acceptance Criteria

1. THE Frontend_UI SHALL display a Mode_Selection_Component with two dropdown controls
2. THE Mode_Selection_Component SHALL display all available Scraping_Modes with user-friendly labels
3. THE Mode_Selection_Component SHALL display all available Antibot_Presets with user-friendly labels
4. WHEN a user selects a Scraping_Mode, THE Frontend_UI SHALL retain the selected value
5. WHEN a user selects an Antibot_Preset, THE Frontend_UI SHALL retain the selected value
6. THE Frontend_UI SHALL allow simultaneous selection of both Scraping_Mode and Antibot_Preset
7. THE Frontend_UI SHALL submit both selected values in the scrape job request

### Requirement 2: User-Friendly Mode Labels

**User Story:** As a non-technical user, I want to see clear descriptions instead of technical mode names, so that I can understand what each option does.

#### Acceptance Criteria

1. THE Frontend_UI SHALL map technical mode name "fast" to user-friendly label "Quick Scan"
2. THE Frontend_UI SHALL map technical mode name "balanced" to user-friendly label "Balanced Scan"
3. THE Frontend_UI SHALL map technical mode name "deep" to user-friendly label "Deep Scan"
4. THE Frontend_UI SHALL map technical mode name "deep_agent" to user-friendly label "AI-Assisted Deep Scan"
5. THE Frontend_UI SHALL map technical mode name "parallel" to user-friendly label "High-Speed Parallel"
6. THE Frontend_UI SHALL map technical mode name "research" to user-friendly label "Research Mode"
7. THE Frontend_UI SHALL map antibot preset "high-stealth" to user-friendly label "Maximum Stealth (0% Detection)"
8. THE Frontend_UI SHALL map antibot preset "balanced" to user-friendly label "Balanced Protection (67% Pass Rate)"
9. THE Frontend_UI SHALL map antibot preset "high-speed" to user-friendly label "Fast & Lightweight"
10. WHEN a user hovers over a mode option, THE Frontend_UI SHALL display a tooltip with detailed description

### Requirement 3: Backend Request Model Extension

**User Story:** As a backend developer, I want the ScrapeStartRequest model to accept both mode and antibot_preset fields, so that the orchestrator can configure both dimensions of scraping behavior.

#### Acceptance Criteria

1. THE ScrapeStartRequest SHALL include a field named "antibot_preset" of type string
2. THE ScrapeStartRequest SHALL validate that "antibot_preset" is one of: "high-stealth", "balanced", "high-speed"
3. THE ScrapeStartRequest SHALL accept "antibot_preset" as optional with default value "balanced"
4. WHEN a ScrapeStartRequest is received, THE Backend_API SHALL parse the "antibot_preset" field
5. THE Backend_API SHALL pass the antibot_preset value to the Configuration_Manager
6. THE Backend_API SHALL pass the mode value to the Orchestrator

### Requirement 4: Hardware Accelerator Detection

**User Story:** As a system administrator, I want the system to automatically detect available GPU/TPU/DPU hardware at startup, so that acceleration is used when available without manual configuration.

#### Acceptance Criteria

1. WHEN the Backend_API starts, THE Hardware_Detector SHALL check for NVIDIA GPU using torch.cuda.is_available()
2. WHEN the Backend_API starts, THE Hardware_Detector SHALL check for AMD GPU using torch.version.hip
3. WHEN the Backend_API starts, THE Hardware_Detector SHALL check for Apple Silicon GPU using torch.backends.mps.is_available()
4. WHEN the Backend_API starts, THE Hardware_Detector SHALL check for Intel GPU using openvino.runtime
5. WHEN the Backend_API starts, THE Hardware_Detector SHALL check for TPU_Device using environment variables TPU_NAME or COLAB_TPU_ADDR
6. THE Hardware_Detector SHALL store detected device type in one of: "nvidia_gpu", "amd_gpu", "apple_gpu", "intel_gpu", "tpu", "cpu"
7. THE Hardware_Detector SHALL log the detected device type to application logs
8. THE Hardware_Detector SHALL complete detection within 2 seconds of startup

### Requirement 5: GPU-Accelerated CAPTCHA Solving

**User Story:** As a scraping job, I want CAPTCHA challenges to be solved using GPU acceleration when available, so that CAPTCHA solving is faster and more reliable.

#### Acceptance Criteria

1. WHEN a CAPTCHA is detected AND a GPU_Device is available, THE CAPTCHA_Solver SHALL use GPU-accelerated OCR models
2. WHEN PaddleOCR is selected, THE CAPTCHA_Solver SHALL pass use_gpu=True to PaddleOCR constructor
3. WHEN EasyOCR is selected, THE CAPTCHA_Solver SHALL pass gpu=True to easyocr.Reader constructor
4. WHEN no GPU_Device is available, THE CAPTCHA_Solver SHALL fall back to CPU-based OCR models
5. THE CAPTCHA_Solver SHALL process CAPTCHA images using the detected GPU_Device when available
6. WHEN GPU_Device is "nvidia_gpu", THE CAPTCHA_Solver SHALL use CUDA acceleration
7. WHEN GPU_Device is "amd_gpu", THE CAPTCHA_Solver SHALL use ROCm acceleration
8. WHEN GPU_Device is "apple_gpu", THE CAPTCHA_Solver SHALL use Metal acceleration

### Requirement 6: Compute Accelerator Integration with Orchestrator

**User Story:** As a backend orchestrator, I want to use the Compute_Accelerator for performance-intensive operations, so that scraping and antibot processing are faster when hardware acceleration is available.

#### Acceptance Criteria

1. THE Orchestrator SHALL initialize the Compute_Accelerator at startup
2. THE Orchestrator SHALL query the Compute_Accelerator for detected device type
3. WHEN generating embeddings for search indexing, THE Orchestrator SHALL delegate to Compute_Accelerator.process_embeddings_with_gpu()
4. WHEN processing ML model inference, THE Orchestrator SHALL use the GPU_Device reported by Compute_Accelerator
5. THE Orchestrator SHALL pass the Compute_Accelerator instance to the CAPTCHA_Solver
6. THE Orchestrator SHALL log GPU utilization events to observability metrics

### Requirement 7: Mode Compatibility Validation API

**User Story:** As a frontend developer, I want an API endpoint that returns valid mode-preset combinations, so that the UI can prevent invalid configurations.

#### Acceptance Criteria

1. THE Backend_API SHALL provide an endpoint at path "/api/modes/available"
2. WHEN a GET request is made to "/api/modes/available", THE Mode_API_Endpoint SHALL return a JSON response
3. THE Mode_API_Endpoint SHALL return a list of all available Scraping_Modes
4. THE Mode_API_Endpoint SHALL return a list of all available Antibot_Presets
5. THE Mode_API_Endpoint SHALL return a compatibility matrix indicating which combinations are valid
6. THE Mode_API_Endpoint SHALL mark "fast" mode + "high-stealth" preset as incompatible
7. THE Mode_API_Endpoint SHALL mark "deep" mode + "high-speed" preset as incompatible
8. THE Mode_API_Endpoint SHALL respond within 100 milliseconds

### Requirement 8: Hardware Detection Status Display

**User Story:** As a user, I want to see which hardware accelerators were detected, so that I know if my jobs will benefit from GPU acceleration.

#### Acceptance Criteria

1. THE Frontend_UI SHALL display a Hardware_Status_Indicator component
2. WHEN a GPU_Device is detected, THE Hardware_Status_Indicator SHALL display the text "Using [device_type] for acceleration"
3. WHEN device_type is "nvidia_gpu", THE Hardware_Status_Indicator SHALL display "Using NVIDIA GPU for acceleration"
4. WHEN device_type is "amd_gpu", THE Hardware_Status_Indicator SHALL display "Using AMD GPU for acceleration"
5. WHEN device_type is "apple_gpu", THE Hardware_Status_Indicator SHALL display "Using Apple Silicon for acceleration"
6. WHEN device_type is "intel_gpu", THE Hardware_Status_Indicator SHALL display "Using Intel GPU for acceleration"
7. WHEN device_type is "tpu", THE Hardware_Status_Indicator SHALL display "Using TPU for acceleration"
8. WHEN device_type is "cpu", THE Hardware_Status_Indicator SHALL display "Using CPU (No GPU detected)"
9. THE Hardware_Status_Indicator SHALL update dynamically when hardware status changes

### Requirement 9: Performance Impact Indicator

**User Story:** As a user, I want to see the expected performance impact of my selected mode and preset combination, so that I can make informed decisions about speed vs stealth tradeoffs.

#### Acceptance Criteria

1. THE Frontend_UI SHALL display a Performance_Indicator component
2. WHEN "fast" mode is selected, THE Performance_Indicator SHALL display "Speed: Very Fast"
3. WHEN "balanced" mode is selected, THE Performance_Indicator SHALL display "Speed: Moderate"
4. WHEN "deep" mode is selected, THE Performance_Indicator SHALL display "Speed: Slow (Thorough)"
5. WHEN "high-stealth" preset is selected, THE Performance_Indicator SHALL display "Stealth: Maximum (Slowest)"
6. WHEN "balanced" preset is selected, THE Performance_Indicator SHALL display "Stealth: Moderate"
7. WHEN "high-speed" preset is selected, THE Performance_Indicator SHALL display "Stealth: Minimal (Fastest)"
8. WHEN both mode and preset are selected, THE Performance_Indicator SHALL display combined impact estimate
9. THE Performance_Indicator SHALL use color coding: green for fast, yellow for moderate, red for slow

### Requirement 10: Active Mode Indicator Display

**User Story:** As a user, I want to see which scraping mode and antibot preset are currently active for running jobs, so that I can verify my configuration was applied correctly.

#### Acceptance Criteria

1. THE Frontend_UI SHALL display an Active_Configuration_Panel component
2. WHEN a scrape job is running, THE Active_Configuration_Panel SHALL display the active Scraping_Mode
3. WHEN a scrape job is running, THE Active_Configuration_Panel SHALL display the active Antibot_Preset
4. WHEN a scrape job is running, THE Active_Configuration_Panel SHALL display the detected GPU_Device type
5. THE Active_Configuration_Panel SHALL update in real-time when job configuration is retrieved
6. THE Active_Configuration_Panel SHALL display mode and preset labels using user-friendly names
7. WHEN no job is running, THE Active_Configuration_Panel SHALL display "No active job"

### Requirement 11: Configuration Persistence

**User Story:** As a user, I want my selected mode and preset preferences to persist across browser sessions, so that I don't have to reconfigure on every visit.

#### Acceptance Criteria

1. WHEN a user selects a Scraping_Mode, THE Frontend_UI SHALL store the selection in browser localStorage
2. WHEN a user selects an Antibot_Preset, THE Frontend_UI SHALL store the selection in browser localStorage
3. WHEN the Frontend_UI loads, THE Frontend_UI SHALL retrieve stored mode from localStorage
4. WHEN the Frontend_UI loads, THE Frontend_UI SHALL retrieve stored preset from localStorage
5. WHEN stored values exist, THE Frontend_UI SHALL pre-populate dropdowns with stored selections
6. WHEN stored values are invalid, THE Frontend_UI SHALL fall back to default values

### Requirement 12: Backend Configuration Manager Integration

**User Story:** As a backend orchestrator, I want to apply antibot preset configurations from the Configuration_Manager, so that all 5 antibot layers are coordinated according to the selected preset.

#### Acceptance Criteria

1. WHEN a scrape job starts, THE Backend_API SHALL retrieve the antibot_preset from ScrapeStartRequest
2. THE Backend_API SHALL pass the antibot_preset to Configuration_Manager.load_preset()
3. THE Configuration_Manager SHALL load preset configuration for "high-stealth", "balanced", or "high-speed"
4. THE Configuration_Manager SHALL configure Layer 1 automation framework selection based on preset
5. THE Configuration_Manager SHALL configure Layer 2 stealth approach based on preset
6. THE Configuration_Manager SHALL configure Layer 3 TLS fingerprint based on preset
7. THE Configuration_Manager SHALL configure Layer 4 device profile based on preset
8. THE Configuration_Manager SHALL configure Layer 5 behavioral simulation based on preset
9. THE Orchestrator SHALL apply the loaded configuration to all antibot layers

### Requirement 13: Mode-Preset Combination Validation

**User Story:** As a backend developer, I want the system to validate mode-preset combinations and reject invalid configurations, so that users cannot submit incompatible configurations.

#### Acceptance Criteria

1. THE Mode_Validator SHALL define compatibility rules for mode-preset combinations
2. WHEN "fast" mode AND "high-stealth" preset are combined, THE Mode_Validator SHALL mark the combination as incompatible
3. WHEN "deep" mode AND "high-speed" preset are combined, THE Mode_Validator SHALL mark the combination as incompatible
4. WHEN an incompatible combination is submitted, THE Backend_API SHALL return HTTP 400 error
5. THE Backend_API SHALL return error message "Mode 'fast' is incompatible with preset 'high-stealth'"
6. WHEN a compatible combination is submitted, THE Backend_API SHALL accept the request
7. THE Mode_Validator SHALL log all validation attempts to application logs

### Requirement 14: Existing Functionality Preservation

**User Story:** As a system administrator, I want all existing scraping modes and antibot features to continue working unchanged, so that existing users are not disrupted.

#### Acceptance Criteria

1. THE Backend_API SHALL continue accepting ScrapeStartRequest without antibot_preset field
2. WHEN antibot_preset field is omitted, THE Backend_API SHALL default to "balanced" preset
3. THE Backend_API SHALL continue supporting all 9 existing Scraping_Modes
4. THE Backend_API SHALL continue supporting all existing discovery_mode values
5. THE Orchestrator SHALL continue coordinating all 5 antibot layers as before
6. THE Compute_Accelerator SHALL remain optional and not block startup if GPU is unavailable
7. WHEN GPU detection fails, THE system SHALL continue operating with CPU-only mode
8. ALL existing API endpoints SHALL remain unchanged in request/response format

### Requirement 15: GPU Detection Error Handling

**User Story:** As a system operator, I want GPU detection failures to be handled gracefully without blocking system startup, so that the system remains available even on systems without GPU libraries.

#### Acceptance Criteria

1. WHEN torch library is not installed, THE Hardware_Detector SHALL catch ImportError and continue
2. WHEN openvino library is not installed, THE Hardware_Detector SHALL catch ImportError and continue
3. WHEN GPU detection raises an exception, THE Hardware_Detector SHALL log the error and default to "cpu"
4. THE Hardware_Detector SHALL not raise exceptions that prevent system startup
5. WHEN all GPU checks fail, THE Hardware_Detector SHALL return device_type "cpu"
6. THE Hardware_Detector SHALL log each detection attempt with result (success/failure)
7. WHEN GPU detection times out after 2 seconds, THE Hardware_Detector SHALL default to "cpu"

### Requirement 16: Frontend Mode Selection API Integration

**User Story:** As a frontend developer, I want the Mode_Selection_Component to fetch available modes from the backend API, so that mode options stay synchronized with backend capabilities.

#### Acceptance Criteria

1. WHEN the Frontend_UI loads, THE Mode_Selection_Component SHALL send GET request to "/api/modes/available"
2. THE Mode_Selection_Component SHALL parse the JSON response into mode and preset lists
3. THE Mode_Selection_Component SHALL populate dropdown options from the parsed response
4. WHEN the API request fails, THE Mode_Selection_Component SHALL display default mode options
5. THE Mode_Selection_Component SHALL cache the API response for 5 minutes
6. THE Mode_Selection_Component SHALL show loading spinner while fetching modes
7. WHEN the API returns incompatible combinations, THE Mode_Selection_Component SHALL disable invalid preset options based on selected mode

### Requirement 17: Hardware Acceleration Configuration API

**User Story:** As a frontend developer, I want an API endpoint that returns hardware acceleration status, so that the UI can display accurate hardware information.

#### Acceptance Criteria

1. THE Backend_API SHALL provide an endpoint at path "/api/hardware/status"
2. WHEN a GET request is made to "/api/hardware/status", THE Backend_API SHALL return current GPU detection status
3. THE Backend_API SHALL return JSON with fields: "device_type", "capabilities", "ocr_acceleration", "embedding_acceleration"
4. THE Backend_API SHALL return "device_type" as one of: "nvidia_gpu", "amd_gpu", "apple_gpu", "intel_gpu", "tpu", "cpu"
5. THE Backend_API SHALL return "ocr_acceleration" as true when GPU_Device is available
6. THE Backend_API SHALL return "embedding_acceleration" as true when GPU_Device or TPU_Device is available
7. THE Backend_API SHALL respond within 50 milliseconds

### Requirement 18: Mode Description Tooltips

**User Story:** As a user, I want detailed descriptions of each mode and preset when I hover over options, so that I can understand the differences between configurations.

#### Acceptance Criteria

1. WHEN a user hovers over "Quick Scan", THE Frontend_UI SHALL display tooltip "Fast scraping with minimal overhead. Best for quick results."
2. WHEN a user hovers over "Balanced Scan", THE Frontend_UI SHALL display tooltip "Default mix of speed and completeness. Recommended for most use cases."
3. WHEN a user hovers over "Deep Scan", THE Frontend_UI SHALL display tooltip "Maximum thoroughness with all checks enabled. Slower but most comprehensive."
4. WHEN a user hovers over "Maximum Stealth", THE Frontend_UI SHALL display tooltip "Uses Camoufox binary patches for 0% detection rate. Slowest but most reliable."
5. WHEN a user hovers over "Balanced Protection", THE Frontend_UI SHALL display tooltip "Uses Patchright with 67% pass rate. Good balance of speed and stealth."
6. WHEN a user hovers over "Fast & Lightweight", THE Frontend_UI SHALL display tooltip "Uses JS-shim for minimal overhead. Fast but lower success rate against strong antibot."
7. THE Frontend_UI SHALL position tooltips above the dropdown to avoid overlapping content
8. THE Frontend_UI SHALL display tooltips within 300 milliseconds of hover

### Requirement 19: GPU Utilization Metrics

**User Story:** As a system operator, I want GPU utilization metrics to be logged and exposed, so that I can monitor hardware acceleration effectiveness.

#### Acceptance Criteria

1. WHEN the Compute_Accelerator processes CAPTCHA with GPU, THE Compute_Accelerator SHALL log processing time in milliseconds
2. WHEN the Compute_Accelerator processes embeddings with GPU, THE Compute_Accelerator SHALL log batch size and processing time
3. THE Compute_Accelerator SHALL increment counter "gpu_captcha_solves_total" for each GPU-accelerated CAPTCHA
4. THE Compute_Accelerator SHALL increment counter "cpu_captcha_solves_total" for each CPU-only CAPTCHA
5. THE Compute_Accelerator SHALL track histogram "gpu_processing_duration_seconds" for GPU operations
6. THE Orchestrator SHALL expose GPU metrics at "/metrics" endpoint in Prometheus format
7. THE Orchestrator SHALL include GPU device type as a label in metrics

### Requirement 20: Preset Override for Job Requests

**User Story:** As an API user, I want to override global antibot preset on a per-job basis, so that I can use different stealth levels for different targets without changing global configuration.

#### Acceptance Criteria

1. WHEN a ScrapeStartRequest includes antibot_preset field, THE Backend_API SHALL use the provided preset for that job only
2. THE Backend_API SHALL not modify global Configuration_Manager preset when processing individual jobs
3. WHEN antibot_preset is provided, THE Backend_API SHALL create a job-specific configuration instance
4. THE Backend_API SHALL apply job-specific configuration to the Orchestrator for that job's execution
5. WHEN the job completes, THE Backend_API SHALL restore default configuration for subsequent jobs
6. THE Backend_API SHALL log preset override events with job_id and selected preset
7. WHEN multiple jobs run concurrently with different presets, THE Backend_API SHALL isolate configurations per job
