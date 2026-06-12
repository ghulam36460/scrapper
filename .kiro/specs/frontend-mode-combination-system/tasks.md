# Implementation Plan: Frontend Mode Combination System

## Overview

This implementation plan converts the Frontend Mode Combination System design into actionable tasks for extending the ASAGUS Scraper v3 to support combined scraping mode and antibot preset selection through an intuitive UI, with automatic GPU/TPU/DPU detection and acceleration. The implementation follows an additive enhancement pattern with zero breaking changes to existing functionality.

The tasks cover:
- Backend enhancements for hardware detection, validation, and preset configuration
- New API endpoints for mode availability and hardware status
- Frontend components for mode selection, hardware status display, and performance indicators
- Integration of GPU acceleration into CAPTCHA solving
- Configuration persistence and user experience improvements

## Tasks

- [ ] 1. Set up backend foundation and hardware detection
  - [ ] 1.1 Enhance Hardware Detector with timeout and error handling
    - Modify `/backend/asagus/layers/compute_accelerator.py`
    - Add 2-second timeout mechanism to prevent blocking startup
    - Implement detection for NVIDIA GPU, AMD GPU, Apple Silicon, Intel GPU, TPU
    - Add comprehensive error handling for missing libraries (torch, openvino)
    - Store detection result in module-level variable for fast access
    - Add detailed logging for each detection attempt
    - Ensure graceful fallback to "cpu" on any failure
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 15.1, 15.2, 15.3, 15.4, 15.5, 15.6, 15.7_

  - [ ] 1.2 Create Mode Validator module
    - Create new file `/backend/asagus/layers/mode_validator.py`
    - Define incompatible combinations: (fast + high-stealth), (deep + high-speed)
    - Implement `validate_combination(mode, preset)` returning ValidationResult
    - Implement `get_compatibility_matrix()` for frontend consumption
    - Add comprehensive logging for validation attempts
    - Create singleton instance for global access
    - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5, 13.6, 13.7, 7.6, 7.7_

  - [ ] 1.3 Extend data models for new API contracts
    - Modify `/backend/asagus/models.py`
    - Add `antibot_preset` field to ScrapeStartRequest with type Literal["high-stealth", "balanced", "high-speed"]
    - Set default value to "balanced" for backward compatibility
    - Create `ModeOption` model with value, label, description fields
    - Create `PresetOption` model with value, label, description, speed_impact fields
    - Create `ModesAvailableResponse` model with modes, presets, compatibility_matrix fields
    - Create `HardwareStatusResponse` model with device_type, capabilities, acceleration flags
    - Add field descriptions for API documentation
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

- [ ] 2. Checkpoint - Ensure all backend foundation tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 3. Implement new API endpoints
  - [ ] 3.1 Initialize Hardware Detector at backend startup
    - Modify `/backend/asagus/main.py`
    - Import HardwareDetector from compute_accelerator
    - Create global instance at module level
    - Call `detect_with_timeout()` during app initialization
    - Store detected device type in runtime state for fast access
    - Add logging for detected hardware
    - Ensure detection completes within 2 seconds
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8_

  - [ ] 3.2 Create GET /api/modes/available endpoint
    - Modify `/backend/asagus/main.py`
    - Define route handler at `/api/modes/available`
    - Use Mode Validator to get compatibility matrix
    - Construct response with user-friendly labels: "Quick Scan" (fast), "Balanced Scan" (balanced), "Deep Scan" (deep)
    - Include all 9 scraping modes and 3 antibot presets
    - Add descriptive tooltips for each option
    - Ensure response time < 100ms
    - Return ModesAvailableResponse with modes, presets, compatibility_matrix
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 7.8, 16.1, 16.2, 16.3_

  - [ ] 3.3 Create GET /api/hardware/status endpoint
    - Modify `/backend/asagus/main.py`
    - Define route handler at `/api/hardware/status`
    - Read device type from global hardware detector instance
    - Construct HardwareStatusResponse with device_type and capabilities
    - Set ocr_acceleration=true for any GPU/TPU device
    - Set embedding_acceleration=true for any GPU/TPU device
    - Ensure response time < 50ms (read from cached value)
    - _Requirements: 17.1, 17.2, 17.3, 17.4, 17.5, 17.6, 17.7_

  - [ ] 3.4 Integrate validation into POST /api/jobs endpoint
    - Modify `/backend/asagus/main.py`
    - Import Mode Validator
    - Extract `antibot_preset` from ScrapeStartRequest
    - Call validator.validate_combination(mode, preset)
    - Return HTTP 400 with descriptive error message if invalid
    - Proceed with job creation if valid
    - Log validation results
    - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5, 13.6, 13.7_

- [ ] 4. Checkpoint - Verify API endpoints functionality
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 5. Integrate GPU acceleration into scraping layers
  - [ ] 5.1 Enhance CAPTCHA Solver with GPU acceleration support
    - Modify `/backend/asagus/layers/captcha_solver.py`
    - Add `hardware_detector` parameter to CAPTCHASolver constructor
    - Query device type from hardware detector during initialization
    - Modify `_solve_with_paddleocr()` to pass `use_gpu=True` when GPU available
    - Modify `_solve_with_easyocr()` to pass `gpu=True` when GPU available
    - Add logging for GPU acceleration status
    - Ensure graceful fallback to CPU when GPU unavailable
    - Support NVIDIA GPU (CUDA), AMD GPU (ROCm), Apple Silicon (Metal)
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8_

  - [ ] 5.2 Integrate Hardware Detector with Antibot Orchestrator
    - Modify `/backend/asagus/layers/antibot_orchestrator.py`
    - Modify orchestrator initialization to accept hardware detector
    - Pass hardware detector to CAPTCHA solver during instantiation
    - Query device type for ML model operations
    - Add GPU utilization logging
    - Ensure backward compatibility when hardware detector is not provided
    - Update job creation code in `/backend/asagus/main.py` to pass hardware detector
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

  - [ ] 5.3 Apply antibot preset configuration in job execution
    - Modify `/backend/asagus/main.py` job execution logic
    - Extract `antibot_preset` from validated ScrapeStartRequest
    - Call `config_manager.load_preset(antibot_preset)`
    - Retrieve loaded configuration
    - Create job-specific orchestrator instance with preset configuration
    - Pass configuration to all 5 antibot layers
    - Log preset application events
    - Ensure configuration isolation between concurrent jobs
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 12.6, 12.7, 12.8, 12.9, 20.1, 20.2, 20.3, 20.4, 20.5, 20.6, 20.7_

- [ ] 6. Checkpoint - Test GPU acceleration integration
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 7. Build frontend mode selection interface
  - [ ] 7.1 Add Mode Selection Component to frontend
    - Modify `/frontend/app/page.tsx`
    - Create inline component ModeSelectionComponent
    - Add state for selectedMode and selectedPreset
    - Fetch available modes from GET /api/modes/available on mount
    - Display two dropdowns with user-friendly labels
    - Filter preset options based on compatibility matrix when mode changes
    - Store selections in component state
    - Add loading spinner while fetching modes
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9, 2.10, 16.1, 16.2, 16.3, 16.4, 16.5, 16.6, 16.7_

  - [ ] 7.2 Add Hardware Status Indicator to frontend
    - Modify `/frontend/app/page.tsx`
    - Create inline component HardwareStatusIndicator
    - Fetch hardware status from GET /api/hardware/status on mount
    - Display device type with appropriate label
    - Show green badge for GPU/TPU detected
    - Show gray badge for CPU only
    - Display text: "Using [GPU Type] for acceleration" or "Using CPU (No GPU detected)"
    - Position near existing status indicators
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7, 8.8, 8.9_

  - [ ] 7.3 Add Performance Indicator Component to frontend
    - Modify `/frontend/app/page.tsx`
    - Create inline component PerformanceIndicator
    - Calculate performance impact based on mode and preset selections
    - Display speed label: "Very Fast", "Moderate", "Slow (Thorough)"
    - Display stealth label: "Maximum", "Moderate", "Minimal"
    - Use color coding: green (fast), yellow (moderate), red (slow)
    - Show combined estimate: "Fast with Moderate Stealth"
    - Update dynamically when selections change
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7, 9.8, 9.9_

- [ ] 8. Checkpoint - Verify frontend components render correctly
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 9. Implement frontend user experience enhancements
  - [ ] 9.1 Implement configuration persistence
    - Modify `/frontend/app/page.tsx`
    - Save selectedMode to localStorage on change
    - Save selectedPreset to localStorage on change
    - Load saved values from localStorage on component mount
    - Pre-populate dropdowns with saved selections
    - Validate saved values against available options
    - Fall back to defaults if saved values are invalid
    - Use keys: "scraper_mode_preference", "antibot_preset_preference"
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 11.6_

  - [ ] 9.2 Add mode description tooltips
    - Modify `/frontend/app/page.tsx`
    - Implement tooltip component or use existing tooltip library
    - Display tooltip on hover over dropdown options
    - Show description text from API response
    - Position tooltips above dropdown to avoid content overlap
    - Add 300ms delay before showing tooltip
    - Include tooltips for all modes and presets
    - _Requirements: 18.1, 18.2, 18.3, 18.4, 18.5, 18.6, 18.7, 18.8_

  - [ ] 9.3 Integrate mode and preset selection into job submission
    - Modify `/frontend/app/page.tsx`
    - Extract selectedMode and selectedPreset from component state
    - Include both fields in ScrapeStartRequest payload
    - Handle validation errors from backend (400 responses)
    - Display error message if combination is invalid
    - Submit request to POST /api/jobs endpoint
    - Ensure backward compatibility with existing job submission code
    - _Requirements: 1.7, 3.4, 3.5, 3.6_

  - [ ] 9.4 Add Active Configuration Display Panel
    - Modify `/frontend/app/page.tsx`
    - Create inline component ActiveConfigurationPanel
    - Fetch current job status to retrieve active configuration
    - Display active scraping mode with user-friendly label
    - Display active antibot preset with user-friendly label
    - Display detected hardware device type
    - Show "No active job" when no job is running
    - Update in real-time when job status changes
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7_

- [ ] 10. Checkpoint - Test complete user flow from selection to submission
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 11. Add observability and monitoring
  - [ ] 11.1 Add GPU utilization metrics and logging
    - Modify `/backend/asagus/layers/compute_accelerator.py`
    - Log processing time for GPU-accelerated CAPTCHA solving
    - Log batch size and processing time for GPU-accelerated embeddings
    - Modify `/backend/asagus/layers/captcha_solver.py`
    - Implement counter "gpu_captcha_solves_total"
    - Implement counter "cpu_captcha_solves_total"
    - Implement histogram "gpu_processing_duration_seconds"
    - Add device type as label in metrics
    - Modify `/backend/asagus/main.py` to expose metrics at /metrics endpoint in Prometheus format
    - _Requirements: 19.1, 19.2, 19.3, 19.4, 19.5, 19.6, 19.7_

- [ ] 12. Testing and validation
  - [ ]* 12.1 Add end-to-end integration test
    - Create new file `/backend/tests/test_mode_combination_system.py`
    - Test GET /api/modes/available endpoint
    - Test GET /api/hardware/status endpoint
    - Test POST /api/jobs with valid mode-preset combination
    - Test POST /api/jobs with invalid combination (expect 400)
    - Test that antibot preset is applied to orchestrator
    - Test GPU acceleration when GPU is available
    - Test CPU fallback when GPU is unavailable

  - [ ]* 12.2 Verify backward compatibility
    - Test existing job submissions without antibot_preset field
    - Verify all 9 scraping modes still work
    - Verify all existing API endpoints are unchanged
    - Test system startup without GPU libraries installed
    - Verify concurrent job execution with different configurations
    - Test that existing antibot orchestrator behavior is preserved
    - Verify no performance regression in CPU-only mode
    - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5, 14.6, 14.7, 14.8_

- [ ] 13. Documentation and user guidance
  - [ ] 13.1 Update API documentation
    - Modify `/backend/README.md` or API documentation files
    - Document GET /api/modes/available endpoint
    - Document GET /api/hardware/status endpoint
    - Document antibot_preset field in POST /api/jobs
    - Add examples for valid and invalid combinations
    - Document error responses for invalid combinations
    - Add GPU acceleration documentation
    - Update existing job submission examples

  - [ ] 13.2 Create user guide for mode combination feature
    - Create new file `/docs/MODE_COMBINATION_GUIDE.md`
    - Explain scraping modes and their use cases
    - Explain antibot presets and their tradeoffs
    - Document which combinations are valid/invalid and why
    - Explain hardware acceleration benefits
    - Provide examples for common scenarios
    - Add screenshots of the UI components
    - Document configuration persistence behavior

- [ ] 14. Final checkpoint - Complete system validation
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability (e.g., _Requirements: X.Y_)
- Checkpoints ensure incremental validation after major implementation phases
- Implementation follows additive enhancement pattern with zero breaking changes
- Hardware detection is non-blocking with 2-second timeout to prevent startup delays
- GPU acceleration is automatic when available, with graceful fallback to CPU
- Configuration isolation ensures concurrent jobs with different presets don't interfere
- Frontend components are implemented as inline components in page.tsx to minimize file changes
- LocalStorage persistence is validated to prevent invalid saved values from breaking the UI
- All API responses include user-friendly labels for non-technical users

## Task Dependency Graph

```json
{
  "waves": [
    {
      "id": 0,
      "tasks": ["1.1", "1.2", "1.3"]
    },
    {
      "id": 1,
      "tasks": ["3.1", "3.2", "3.3"]
    },
    {
      "id": 2,
      "tasks": ["3.4", "5.1"]
    },
    {
      "id": 3,
      "tasks": ["5.2", "5.3"]
    },
    {
      "id": 4,
      "tasks": ["7.1", "7.2", "7.3"]
    },
    {
      "id": 5,
      "tasks": ["9.1", "9.2", "9.3", "9.4"]
    },
    {
      "id": 6,
      "tasks": ["11.1"]
    },
    {
      "id": 7,
      "tasks": ["12.1", "12.2", "13.1", "13.2"]
    }
  ]
}
```
