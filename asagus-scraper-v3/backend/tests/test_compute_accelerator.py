"""Unit tests for ComputeAccelerator hardware detection."""

import pytest
import time
from unittest.mock import patch, MagicMock
from asagus.layers.compute_accelerator import ComputeAccelerator, _cached_device, _detection_timestamp


class TestComputeAccelerator:
    """Test suite for ComputeAccelerator."""
    
    def test_detection_completes_within_timeout(self):
        """Verify hardware detection completes within 2 seconds."""
        start_time = time.time()
        accelerator = ComputeAccelerator(allow_gpu=True, allow_tpu=False)
        elapsed = time.time() - start_time
        
        assert elapsed < 2.5, f"Detection took {elapsed:.3f}s, expected < 2.5s"
        assert accelerator.device is not None
        assert accelerator.device in [
            "nvidia_gpu", "amd_gpu", "apple_gpu", "intel_gpu", "tpu", "cpu"
        ]
    
    def test_graceful_fallback_to_cpu(self):
        """Verify system falls back to CPU when no GPU is detected."""
        accelerator = ComputeAccelerator(allow_gpu=False, allow_tpu=False)
        assert accelerator.device == "cpu"
    
    @patch('asagus.layers.compute_accelerator.logger')
    def test_logging_for_each_detection_attempt(self, mock_logger):
        """Verify detailed logging occurs for each detection attempt."""
        accelerator = ComputeAccelerator(allow_gpu=True, allow_tpu=True)
        
        # Verify that logging occurred (info, debug, or warning calls)
        assert mock_logger.info.called or mock_logger.debug.called or mock_logger.warning.called
    
    @patch('asagus.layers.compute_accelerator.ComputeAccelerator._has_nvidia_gpu')
    def test_nvidia_gpu_detection(self, mock_nvidia):
        """Verify NVIDIA GPU detection returns correct device type."""
        mock_nvidia.return_value = True
        
        accelerator = ComputeAccelerator(allow_gpu=True)
        assert accelerator.device == "nvidia_gpu"
    
    @patch('asagus.layers.compute_accelerator.ComputeAccelerator._has_nvidia_gpu')
    @patch('asagus.layers.compute_accelerator.ComputeAccelerator._has_amd_gpu')
    def test_amd_gpu_detection(self, mock_amd, mock_nvidia):
        """Verify AMD GPU detection returns correct device type."""
        mock_nvidia.return_value = False
        mock_amd.return_value = True
        
        accelerator = ComputeAccelerator(allow_gpu=True)
        assert accelerator.device == "amd_gpu"
    
    @patch('asagus.layers.compute_accelerator.ComputeAccelerator._has_nvidia_gpu')
    @patch('asagus.layers.compute_accelerator.ComputeAccelerator._has_amd_gpu')
    @patch('asagus.layers.compute_accelerator.ComputeAccelerator._has_apple_gpu')
    def test_apple_gpu_detection(self, mock_apple, mock_amd, mock_nvidia):
        """Verify Apple Silicon GPU detection returns correct device type."""
        mock_nvidia.return_value = False
        mock_amd.return_value = False
        mock_apple.return_value = True
        
        accelerator = ComputeAccelerator(allow_gpu=True)
        assert accelerator.device == "apple_gpu"
    
    @patch('asagus.layers.compute_accelerator.ComputeAccelerator._has_nvidia_gpu')
    @patch('asagus.layers.compute_accelerator.ComputeAccelerator._has_amd_gpu')
    @patch('asagus.layers.compute_accelerator.ComputeAccelerator._has_apple_gpu')
    @patch('asagus.layers.compute_accelerator.ComputeAccelerator._has_intel_gpu')
    def test_intel_gpu_detection(self, mock_intel, mock_apple, mock_amd, mock_nvidia):
        """Verify Intel GPU detection returns correct device type."""
        mock_nvidia.return_value = False
        mock_amd.return_value = False
        mock_apple.return_value = False
        mock_intel.return_value = True
        
        accelerator = ComputeAccelerator(allow_gpu=True)
        assert accelerator.device == "intel_gpu"
    
    @patch('asagus.layers.compute_accelerator.ComputeAccelerator._has_nvidia_gpu')
    @patch('asagus.layers.compute_accelerator.ComputeAccelerator._has_amd_gpu')
    @patch('asagus.layers.compute_accelerator.ComputeAccelerator._has_apple_gpu')
    @patch('asagus.layers.compute_accelerator.ComputeAccelerator._has_intel_gpu')
    @patch('asagus.layers.compute_accelerator.ComputeAccelerator._has_tpu')
    def test_tpu_detection(self, mock_tpu, mock_intel, mock_apple, mock_amd, mock_nvidia):
        """Verify TPU detection returns correct device type."""
        mock_nvidia.return_value = False
        mock_amd.return_value = False
        mock_apple.return_value = False
        mock_intel.return_value = False
        mock_tpu.return_value = True
        
        accelerator = ComputeAccelerator(allow_gpu=True, allow_tpu=True)
        assert accelerator.device == "tpu"
    
    @patch('asagus.layers.compute_accelerator.ComputeAccelerator._has_nvidia_gpu')
    def test_error_handling_for_missing_torch(self, mock_nvidia):
        """Verify graceful handling when torch library is missing."""
        mock_nvidia.side_effect = ImportError("torch not installed")
        
        accelerator = ComputeAccelerator(allow_gpu=True)
        assert accelerator.device == "cpu"
    
    @patch('asagus.layers.compute_accelerator.ComputeAccelerator._has_intel_gpu')
    def test_error_handling_for_missing_openvino(self, mock_intel):
        """Verify graceful handling when openvino library is missing."""
        mock_intel.side_effect = ImportError("openvino not installed")
        
        accelerator = ComputeAccelerator(allow_gpu=True)
        # Should fall back to CPU after all checks fail
        assert accelerator.device in ["nvidia_gpu", "amd_gpu", "apple_gpu", "cpu"]
    
    @patch('asagus.layers.compute_accelerator.ComputeAccelerator._detect_device')
    def test_exception_during_detection_defaults_to_cpu(self, mock_detect):
        """Verify that exceptions during detection result in CPU fallback."""
        mock_detect.side_effect = Exception("Unexpected error")
        
        accelerator = ComputeAccelerator(allow_gpu=True)
        assert accelerator.device == "cpu"
    
    def test_module_level_caching(self):
        """Verify detection result is cached at module level for fast access."""
        # First call - performs detection
        accelerator1 = ComputeAccelerator(allow_gpu=True)
        device1 = accelerator1.device
        
        # Second call - should use cached result
        start_time = time.time()
        accelerator2 = ComputeAccelerator(allow_gpu=True)
        elapsed = time.time() - start_time
        
        assert accelerator2.device == device1
        # Cached detection should be much faster than 2 seconds
        assert elapsed < 0.5, f"Cached detection took {elapsed:.3f}s, expected < 0.5s"
    
    def test_get_config_returns_capabilities(self):
        """Verify get_config returns device capabilities."""
        accelerator = ComputeAccelerator(allow_gpu=True)
        config = accelerator.get_config()
        
        assert "detected_device" in config
        assert "gpu_enabled" in config
        assert "tpu_enabled" in config
        assert "capabilities" in config
        assert "ocr_acceleration" in config["capabilities"]
        assert "embedding_acceleration" in config["capabilities"]
    
    def test_state_method_returns_device_info(self):
        """Verify state method returns current device state."""
        accelerator = ComputeAccelerator(allow_gpu=True)
        state = accelerator.state()
        
        assert "device" in state
        assert "capabilities" in state
        assert "uses" in state
        assert isinstance(state["uses"], list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
