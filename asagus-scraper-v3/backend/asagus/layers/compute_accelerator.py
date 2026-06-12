"""GPU/TPU/DPU acceleration detection and usage."""

from __future__ import annotations

import logging
import os
import sys
import time
from importlib.util import find_spec
from typing import Literal

# Module-level cached detection result for fast access
_cached_device: str | None = None
_detection_timestamp: float = 0.0
_cached_detection_key: tuple[object, ...] | None = None

logger = logging.getLogger(__name__)


class ComputeAccelerator:
    """
    Detect and use GPU/TPU/DPU for acceleration.
    Useful for CAPTCHA solving, embeddings, and ML inference.
    """

    # Detection timeout in seconds to prevent blocking startup
    DETECTION_TIMEOUT_SECONDS: float = 2.0

    def __init__(self, allow_gpu: bool = True, allow_tpu: bool = False):
        self.allow_gpu = allow_gpu
        self.allow_tpu = allow_tpu
        self.device = self._detect_device_with_timeout()

    def _detect_device_with_timeout(self) -> str:
        """
        Detect available accelerator with timeout protection.
        
        Uses module-level caching to avoid repeated detection.
        Ensures detection completes within DETECTION_TIMEOUT_SECONDS.
        """
        global _cached_device, _detection_timestamp, _cached_detection_key
        cache_key = self._cache_key()
        
        # Return cached result if available and recent (within 60 seconds)
        if _cached_device is not None and _cached_detection_key == cache_key and (time.time() - _detection_timestamp) < 60:
            logger.debug(f"Using cached device detection result: {_cached_device}")
            return _cached_device
        
        start_time = time.time()
        detected_device = "cpu"
        
        try:
            detected_device = self._detect_device(start_time)
        except Exception as e:
            logger.error(f"Hardware detection encountered unexpected error: {e}", exc_info=True)
            detected_device = "cpu"
        
        elapsed = time.time() - start_time
        logger.info(f"Hardware detection completed in {elapsed:.3f}s: {detected_device}")
        
        # Cache the result
        _cached_device = detected_device
        _cached_detection_key = cache_key
        _detection_timestamp = time.time()
        
        return detected_device

    def _cache_key(self) -> tuple[object, ...]:
        detector_names = (
            "_detect_device",
            "_has_nvidia_gpu",
            "_has_amd_gpu",
            "_has_apple_gpu",
            "_has_intel_gpu",
            "_has_tpu",
        )
        detector_signature = tuple(id(getattr(type(self), name)) for name in detector_names)
        return (self.allow_gpu, self.allow_tpu, detector_signature)

    def _heavy_probe_enabled(self) -> bool:
        return os.getenv("ASAGUS_ENABLE_HEAVY_ACCELERATOR_PROBES", "").lower() in {"1", "true", "yes", "on"}

    def _can_import_heavy_probe(self, module_name: str) -> bool:
        if module_name in sys.modules:
            return True
        if not self._heavy_probe_enabled():
            logger.debug(
                "%s probe skipped to keep startup fast; set ASAGUS_ENABLE_HEAVY_ACCELERATOR_PROBES=1 to enable imports",
                module_name,
            )
            return False
        return find_spec(module_name) is not None

    def _detect_device(self, start_time: float) -> str:
        """
        Detect available accelerator with timeout checks.
        
        Args:
            start_time: Timestamp when detection started
            
        Returns:
            Device type string: "nvidia_gpu", "amd_gpu", "apple_gpu", "intel_gpu", "tpu", or "cpu"
        """
        if not self.allow_gpu:
            logger.info("GPU detection disabled by configuration")
            return "cpu"

        # Check NVIDIA GPU first (most common)
        if self._check_timeout(start_time, "nvidia"):
            if self._has_nvidia_gpu():
                return "nvidia_gpu"

        # Check AMD GPU (ROCm)
        if self._check_timeout(start_time, "amd"):
            if self._has_amd_gpu():
                return "amd_gpu"

        # Check Apple Silicon (Metal)
        if self._check_timeout(start_time, "apple"):
            if self._has_apple_gpu():
                return "apple_gpu"

        # Check Intel GPU (OpenVINO)
        if self._check_timeout(start_time, "intel"):
            if self._has_intel_gpu():
                return "intel_gpu"

        # Check TPU
        if self.allow_tpu and self._check_timeout(start_time, "tpu"):
            if self._has_tpu():
                return "tpu"

        logger.info("No GPU/TPU detected, using CPU")
        return "cpu"

    def _check_timeout(self, start_time: float, device_name: str) -> bool:
        """
        Check if detection timeout has been exceeded.
        
        Args:
            start_time: Timestamp when detection started
            device_name: Name of device being checked (for logging)
            
        Returns:
            True if still within timeout, False if timeout exceeded
        """
        elapsed = time.time() - start_time
        if elapsed >= self.DETECTION_TIMEOUT_SECONDS:
            logger.warning(
                f"Hardware detection timeout exceeded ({elapsed:.3f}s >= {self.DETECTION_TIMEOUT_SECONDS}s), "
                f"skipping {device_name} check"
            )
            return False
        return True

    def _has_nvidia_gpu(self) -> bool:
        """
        Check for NVIDIA GPU with comprehensive error handling.
        
        Returns:
            True if NVIDIA GPU is available, False otherwise
        """
        try:
            if not self._can_import_heavy_probe("torch"):
                return False
            import torch
            is_available = torch.cuda.is_available()
            if is_available:
                logger.info("NVIDIA GPU detected (CUDA available)")
            else:
                logger.debug("NVIDIA GPU check: torch installed but CUDA not available")
            return is_available
        except ImportError:
            logger.debug("NVIDIA GPU check: torch library not installed")
            return False
        except Exception as e:
            logger.warning(f"NVIDIA GPU detection error: {e}")
            return False

    def _has_amd_gpu(self) -> bool:
        """
        Check for AMD GPU (ROCm) with comprehensive error handling.
        
        Returns:
            True if AMD GPU is available, False otherwise
        """
        try:
            if not self._can_import_heavy_probe("torch"):
                return False
            import torch
            is_available = torch.version.hip is not None
            if is_available:
                logger.info("AMD GPU detected (ROCm available)")
            else:
                logger.debug("AMD GPU check: torch installed but ROCm not available")
            return is_available
        except ImportError:
            logger.debug("AMD GPU check: torch library not installed")
            return False
        except AttributeError:
            logger.debug("AMD GPU check: torch.version.hip attribute not available")
            return False
        except Exception as e:
            logger.warning(f"AMD GPU detection error: {e}")
            return False

    def _has_apple_gpu(self) -> bool:
        """
        Check for Apple Silicon (Metal) with comprehensive error handling.
        
        Returns:
            True if Apple Silicon GPU is available, False otherwise
        """
        try:
            import platform
            if platform.system() != "Darwin":
                logger.debug("Apple GPU check: not running on macOS")
                return False
            if not self._can_import_heavy_probe("torch"):
                return False
            
            import torch
            is_available = torch.backends.mps.is_available()
            if is_available:
                logger.info("Apple Silicon GPU detected (Metal Performance Shaders available)")
            else:
                logger.debug("Apple GPU check: running on macOS but MPS not available")
            return is_available
        except ImportError:
            logger.debug("Apple GPU check: torch library not installed")
            return False
        except Exception as e:
            logger.warning(f"Apple GPU detection error: {e}")
            return False

    def _has_intel_gpu(self) -> bool:
        """
        Check for Intel GPU (oneAPI/OpenVINO) with comprehensive error handling.
        
        Returns:
            True if Intel GPU is available, False otherwise
        """
        try:
            if not self._can_import_heavy_probe("openvino"):
                return False
            from openvino.runtime import Core
            core = Core()
            devices = core.available_devices
            is_available = any("GPU" in d for d in devices)
            if is_available:
                logger.info(f"Intel GPU detected (OpenVINO devices: {devices})")
            else:
                logger.debug(f"Intel GPU check: OpenVINO installed but no GPU found (devices: {devices})")
            return is_available
        except ImportError:
            logger.debug("Intel GPU check: openvino library not installed")
            return False
        except Exception as e:
            logger.warning(f"Intel GPU detection error: {e}")
            return False

    def _has_tpu(self) -> bool:
        """
        Check for Google Cloud TPU with comprehensive error handling.
        
        Returns:
            True if TPU is available, False otherwise
        """
        try:
            is_available = "TPU_NAME" in os.environ or "COLAB_TPU_ADDR" in os.environ
            if is_available:
                tpu_name = os.environ.get("TPU_NAME") or os.environ.get("COLAB_TPU_ADDR")
                logger.info(f"TPU detected (TPU_NAME/COLAB_TPU_ADDR: {tpu_name})")
            else:
                logger.debug("TPU check: TPU_NAME and COLAB_TPU_ADDR environment variables not set")
            return is_available
        except Exception as e:
            logger.warning(f"TPU detection error: {e}")
            return False

    async def solve_captcha_with_gpu(
        self,
        image_path: str,
        model_name: str = "paddleocr",
    ) -> str:
        """Use GPU to solve OCR-based CAPTCHA."""
        device = self.device

        if model_name == "paddleocr":
            return await self._solve_with_paddleocr(image_path, device)
        elif model_name == "easyocr":
            return await self._solve_with_easyocr(image_path, device)

        return ""

    async def _solve_with_paddleocr(self, image_path: str, device: str) -> str:
        """Use PaddleOCR with GPU acceleration."""
        try:
            from paddleocr import PaddleOCR
            use_gpu = device != "cpu"
            ocr = PaddleOCR(use_gpu=use_gpu, lang="en")
            result = ocr.ocr(image_path)
            return " ".join([line[0][1] for line in result[0]]) if result else ""
        except ImportError:
            return ""

    async def _solve_with_easyocr(self, image_path: str, device: str) -> str:
        """Use EasyOCR with GPU acceleration."""
        try:
            import easyocr
            reader = easyocr.Reader(["en"], gpu=(device != "cpu"))
            results = reader.readtext(image_path)
            return " ".join([text[1] for text in results])
        except ImportError:
            return ""

    async def process_embeddings_with_gpu(self, texts: list[str]) -> list:
        """Use GPU for embedding generation."""
        device = self.device

        if device == "cpu":
            return await self._embeddings_cpu(texts)

        try:
            from sentence_transformers import SentenceTransformer
            device_map = "cuda" if "gpu" in device else "cpu"
            model = SentenceTransformer("all-MiniLM-L6-v2", device=device_map)
            return model.encode(texts)
        except ImportError:
            return await self._embeddings_cpu(texts)

    async def _embeddings_cpu(self, texts: list[str]) -> list:
        """Fallback to CPU embeddings."""
        try:
            from sentence_transformers import SentenceTransformer
            model = SentenceTransformer("all-MiniLM-L6-v2")
            return model.encode(texts)
        except ImportError:
            return []

    def get_config(self) -> dict[str, object]:
        """Get acceleration configuration."""
        return {
            "detected_device": self.device,
            "gpu_enabled": self.allow_gpu,
            "tpu_enabled": self.allow_tpu,
            "capabilities": {
                "ocr_acceleration": "gpu" in self.device,
                "embedding_acceleration": "gpu" in self.device or "tpu" in self.device,
                "ml_inference": "gpu" in self.device or "tpu" in self.device,
            },
        }

    def state(self) -> dict[str, object]:
        return {
            "device": self.device,
            "capabilities": self.get_config()["capabilities"],
            "uses": [
                "captcha_ocr_solving",
                "embedding_generation",
                "ml_model_inference",
                "computer_vision_tasks",
            ],
        }
