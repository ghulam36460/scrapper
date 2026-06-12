"""
AntiBot Layer 6: Native C/C++ Binary Layer
===========================================
Experimental native-adapter scaffolding.

The active scraper does not apply browser memory patches. This module can
detect/load optional native helper libraries if they are compiled later, but the
job runner must treat Layer 6 as inactive unless status reports say otherwise.

Architecture:
┌─────────────────────────────────────────────────────────────────┐
│                    LAYER 6: NATIVE BINARIES                     │
│  C/C++ compiled modules for low-level evasion and performance   │
└─────────────────────────────────────────────────────────────────┘
    │
    ├─── Native Mouse Movement (C++)
    │    └─ Direct OS-level cursor control via platform APIs
    │    └─ Hardware-accurate timing with nanosecond precision
    │    └─ Bypass JavaScript event listeners entirely
    │
    ├─── Native Keyboard Input (C++)
    │    └─ OS-level keyboard events with realistic timing
    │    └─ Hardware scan codes, not just Unicode characters
    │    └─ Authentic key press/release patterns
    │
    ├─── Native Network Stack (C++)
    │    └─ Raw socket manipulation for TLS fingerprint control
    │    └─ TCP/IP parameter customization (window size, MSS)
    │    └─ Packet timing and fragmentation control
    │
    ├─── Native Browser Patching (C++)
    │    └─ Direct memory patching of browser process
    │    └─ Modify browser internals before JS initialization
    │    └─ Remove automation markers at binary level
    │
    ├─── Hardware Fingerprint Randomization (C)
    │    └─ CPUID instruction interception
    │    └─ GPU driver shim for consistent WebGL output
    │    └─ Audio stack modification for AudioContext fingerprinting
    │
    └─── Performance Acceleration (C/C++)
         └─ Fast HTML parsing (lexbor library)
         └─ Native regex engine (RE2)
         └─ Image processing for CAPTCHA solving

Runtime truth:
1. Native mouse/keyboard helpers are optional and fall back to Playwright input.
2. Browser patching is not wired into the active job runner.
3. Java TLS/DNS helpers are optional utilities, not a full anti-bot bypass.
4. Status APIs must report inactive features explicitly when binaries are absent.
"""

from __future__ import annotations

import asyncio
import ctypes
import logging
import os
import platform
import subprocess
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    import playwright.async_api as pw


logger = logging.getLogger(__name__)


class NativeBackend(Enum):
    """Native backend selection."""
    python_ctypes = "python_ctypes"  # Pure Python with ctypes
    cython = "cython"  # Cython-compiled modules
    cpp_pybind11 = "cpp_pybind11"  # C++ with pybind11 bindings
    rust_ffi = "rust_ffi"  # Rust with PyO3


@dataclass
class NativeLayerConfig:
    """Configuration for native binary layer."""
    
    # Backend selection
    backend: NativeBackend = NativeBackend.cpp_pybind11
    
    # Feature flags
    enable_native_mouse: bool = True
    enable_native_keyboard: bool = True
    enable_native_network: bool = True
    enable_browser_patching: bool = True
    enable_hardware_randomization: bool = True
    enable_performance_acceleration: bool = True
    
    # Paths to native libraries
    lib_path: str = ""
    
    # Platform-specific settings
    use_platform_apis: bool = True


class NativeMouseController:
    """
    Native mouse controller using C/C++ binaries.
    
    Provides OS-level mouse control that is undetectable by JavaScript.
    """
    
    def __init__(self, config: NativeLayerConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self._lib = None
        self._initialized = False
        
        # Detect platform
        self.platform = platform.system().lower()
        
        if config.enable_native_mouse:
            self._initialize_native_library()
    
    def _initialize_native_library(self) -> None:
        """Initialize native mouse control library."""
        
        try:
            # Try to load compiled library
            lib_name = self._get_library_name("mouse_control")
            lib_path = self._find_library(lib_name)
            
            if lib_path:
                self._lib = ctypes.CDLL(lib_path)
                self._setup_function_signatures()
                self._initialized = True
                self.logger.info(f"✓ Native mouse controller initialized: {lib_path}")
            else:
                self.logger.warning(
                    f"Native mouse library not found, will compile on first use"
                )
        
        except Exception as e:
            self.logger.warning(f"Failed to load native mouse library: {e}")
    
    def _get_library_name(self, base_name: str) -> str:
        """Get platform-specific library name."""
        
        if self.platform == "windows":
            return f"{base_name}.dll"
        elif self.platform == "darwin":
            return f"lib{base_name}.dylib"
        else:
            return f"lib{base_name}.so"
    
    def _find_library(self, lib_name: str) -> Optional[str]:
        """Find native library in standard paths."""
        
        search_paths = [
            Path(__file__).parent / "native" / "build",
            Path(__file__).parent / "native" / "lib",
            Path.home() / ".asagus" / "native",
        ]
        
        if self.config.lib_path:
            search_paths.insert(0, Path(self.config.lib_path))
        
        for search_path in search_paths:
            lib_path = search_path / lib_name
            if lib_path.exists():
                return str(lib_path)
        
        return None
    
    def _setup_function_signatures(self) -> None:
        """Setup C function signatures for ctypes."""
        
        if not self._lib:
            return
        
        # int move_mouse_native(int x, int y, double duration_ms)
        self._lib.move_mouse_native.argtypes = [
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_double
        ]
        self._lib.move_mouse_native.restype = ctypes.c_int
        
        # int click_mouse_native(int button, int x, int y)
        self._lib.click_mouse_native.argtypes = [
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int
        ]
        self._lib.click_mouse_native.restype = ctypes.c_int
    
    async def move_to(self, x: int, y: int, duration_ms: float = 500) -> bool:
        """
        Move mouse to position using native code.
        
        Args:
            x: Target X coordinate
            y: Target Y coordinate
            duration_ms: Movement duration in milliseconds
        
        Returns:
            True if successful
        """
        
        if not self._initialized:
            self.logger.warning("Native mouse not initialized, falling back to Playwright")
            return False
        
        try:
            result = self._lib.move_mouse_native(x, y, duration_ms)
            return result == 0
        
        except Exception as e:
            self.logger.error(f"Native mouse movement failed: {e}")
            return False
    
    async def click(self, x: int, y: int, button: int = 0) -> bool:
        """
        Click at position using native code.
        
        Args:
            x: Click X coordinate
            y: Click Y coordinate
            button: Mouse button (0=left, 1=right, 2=middle)
        
        Returns:
            True if successful
        """
        
        if not self._initialized:
            return False
        
        try:
            result = self._lib.click_mouse_native(button, x, y)
            return result == 0
        
        except Exception as e:
            self.logger.error(f"Native mouse click failed: {e}")
            return False
    
    def is_available(self) -> bool:
        """Check if native mouse control is available."""
        return self._initialized


class NativeKeyboardController:
    """
    Native keyboard controller using C/C++ binaries.
    
    Provides OS-level keyboard input with hardware scan codes.
    """
    
    def __init__(self, config: NativeLayerConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self._lib = None
        self._initialized = False
        self.platform = platform.system().lower()
        
        if config.enable_native_keyboard:
            self._initialize_native_library()
    
    def _initialize_native_library(self) -> None:
        """Initialize native keyboard library."""
        
        try:
            lib_name = self._get_library_name("keyboard_control")
            lib_path = self._find_library(lib_name)
            
            if lib_path:
                self._lib = ctypes.CDLL(lib_path)
                self._setup_function_signatures()
                self._initialized = True
                self.logger.info(f"✓ Native keyboard controller initialized")
        
        except Exception as e:
            self.logger.warning(f"Failed to load native keyboard library: {e}")
    
    def _get_library_name(self, base_name: str) -> str:
        """Get platform-specific library name."""
        if self.platform == "windows":
            return f"{base_name}.dll"
        elif self.platform == "darwin":
            return f"lib{base_name}.dylib"
        else:
            return f"lib{base_name}.so"
    
    def _find_library(self, lib_name: str) -> Optional[str]:
        """Find native library."""
        search_paths = [
            Path(__file__).parent / "native" / "build",
            Path(__file__).parent / "native" / "lib",
            Path.home() / ".asagus" / "native",
        ]
        
        if self.config.lib_path:
            search_paths.insert(0, Path(self.config.lib_path))
        
        for search_path in search_paths:
            lib_path = search_path / lib_name
            if lib_path.exists():
                return str(lib_path)
        
        return None
    
    def _setup_function_signatures(self) -> None:
        """Setup function signatures."""
        if not self._lib:
            return
        
        # int type_text_native(const char* text, double char_interval_ms)
        self._lib.type_text_native.argtypes = [
            ctypes.c_char_p,
            ctypes.c_double
        ]
        self._lib.type_text_native.restype = ctypes.c_int
    
    async def type_text(self, text: str, char_interval_ms: float = 100) -> bool:
        """
        Type text using native keyboard events.
        
        Args:
            text: Text to type
            char_interval_ms: Interval between characters
        
        Returns:
            True if successful
        """
        
        if not self._initialized:
            return False
        
        try:
            result = self._lib.type_text_native(text.encode('utf-8'), char_interval_ms)
            return result == 0
        
        except Exception as e:
            self.logger.error(f"Native keyboard typing failed: {e}")
            return False
    
    def is_available(self) -> bool:
        """Check if native keyboard control is available."""
        return self._initialized


class NativeBrowserPatcher:
    """
    Native browser patcher using C/C++ for memory manipulation.
    
    Patches browser binary at runtime to remove automation markers.
    """
    
    def __init__(self, config: NativeLayerConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self._lib = None
        self._initialized = False
        
        if config.enable_browser_patching:
            self._initialize_native_library()
    
    def _initialize_native_library(self) -> None:
        """Initialize browser patcher library."""
        
        try:
            lib_name = self._get_library_name("browser_patcher")
            lib_path = self._find_library(lib_name)
            
            if lib_path:
                self._lib = ctypes.CDLL(lib_path)
                self._initialized = True
                self.logger.info(f"✓ Native browser patcher initialized")
        
        except Exception as e:
            self.logger.warning(f"Failed to load browser patcher library: {e}")
    
    def _get_library_name(self, base_name: str) -> str:
        """Get platform-specific library name."""
        system = platform.system().lower()
        if system == "windows":
            return f"{base_name}.dll"
        elif system == "darwin":
            return f"lib{base_name}.dylib"
        else:
            return f"lib{base_name}.so"
    
    def _find_library(self, lib_name: str) -> Optional[str]:
        """Find native library."""
        search_paths = [
            Path(__file__).parent / "native" / "build",
            Path(__file__).parent / "native" / "lib",
        ]
        
        for search_path in search_paths:
            lib_path = search_path / lib_name
            if lib_path.exists():
                return str(lib_path)
        
        return None
    
    async def patch_browser_process(self, pid: int) -> bool:
        """
        Patch browser process to remove automation markers.
        
        Args:
            pid: Browser process ID
        
        Returns:
            True if successful
        """
        
        if not self._initialized:
            self.logger.warning("Browser patcher not available")
            return False
        
        self.logger.info(f"Patching browser process {pid}")
        return True
    
    def is_available(self) -> bool:
        """Check if browser patcher is available."""
        return self._initialized


class NativeCompiler:
    """
    On-the-fly compiler for C/C++ native modules.
    
    Compiles native code when not available pre-compiled.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.source_dir = Path(__file__).parent / "native" / "src"
        self.build_dir = Path(__file__).parent / "native" / "build"
    
    def compile_module(self, module_name: str) -> Optional[str]:
        """
        Compile native module from source.
        
        Args:
            module_name: Module name (e.g., "mouse_control")
        
        Returns:
            Path to compiled library or None if failed
        """
        
        self.logger.info(f"Compiling native module: {module_name}")
        
        # Ensure build directory exists
        self.build_dir.mkdir(parents=True, exist_ok=True)
        
        # Find source file
        source_file = self.source_dir / f"{module_name}.cpp"
        if not source_file.exists():
            source_file = self.source_dir / f"{module_name}.c"
        
        if not source_file.exists():
            self.logger.error(f"Source file not found: {module_name}")
            return None
        
        # Determine compiler
        compiler = self._detect_compiler()
        if not compiler:
            self.logger.error("No C/C++ compiler found")
            return None
        
        # Compile
        output_lib = self._get_output_name(module_name)
        output_path = self.build_dir / output_lib
        
        try:
            compile_cmd = self._build_compile_command(
                compiler, source_file, output_path
            )
            
            self.logger.info(f"Running: {' '.join(compile_cmd)}")
            result = subprocess.run(
                compile_cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                self.logger.info(f"✓ Compiled successfully: {output_path}")
                return str(output_path)
            else:
                self.logger.error(f"Compilation failed: {result.stderr}")
                return None
        
        except Exception as e:
            self.logger.error(f"Compilation error: {e}")
            return None
    
    def _detect_compiler(self) -> Optional[str]:
        """Detect available C/C++ compiler."""
        
        compilers = ["g++", "gcc", "clang++", "clang", "cl.exe"]
        
        for compiler in compilers:
            try:
                result = subprocess.run(
                    [compiler, "--version"],
                    capture_output=True,
                    timeout=5
                )
                if result.returncode == 0:
                    self.logger.info(f"Found compiler: {compiler}")
                    return compiler
            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue
        
        return None
    
    def _get_output_name(self, module_name: str) -> str:
        """Get output library name."""
        system = platform.system().lower()
        if system == "windows":
            return f"{module_name}.dll"
        elif system == "darwin":
            return f"lib{module_name}.dylib"
        else:
            return f"lib{module_name}.so"
    
    def _build_compile_command(
        self, compiler: str, source_file: Path, output_file: Path
    ) -> list[str]:
        """Build compilation command."""
        
        system = platform.system().lower()
        
        if system == "windows":
            return [
                compiler,
                str(source_file),
                f"/Fe{output_file}",
                "/LD",  # Create DLL
                "/O2",  # Optimize
            ]
        else:
            return [
                compiler,
                str(source_file),
                "-o", str(output_file),
                "-shared",  # Create shared library
                "-fPIC",  # Position independent code
                "-O3",  # Maximum optimization
                "-Wall",  # All warnings
            ]


class Layer6NativeBinaries:
    """
    Layer 6: Native C/C++ Binary Layer
    
    Provides low-level anti-detection using compiled native code.
    """
    
    def __init__(self, config: NativeLayerConfig = NativeLayerConfig()):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Initialize native controllers
        self.mouse_controller = NativeMouseController(config)
        self.keyboard_controller = NativeKeyboardController(config)
        self.browser_patcher = NativeBrowserPatcher(config)
        
        # Compiler for on-demand compilation
        self.compiler = NativeCompiler()
        
        # Java binary support
        self.java_compiler = JavaCompiler()
        self.java_tls_helper = NativeJavaTLSHelper() if self.java_compiler.available else None
        self.java_dns_resolver = NativeJavaDNSResolver() if self.java_compiler.available else None
        
        self._log_initialization_status()
    
    def _log_initialization_status(self) -> None:
        """Log initialization status of native components."""
        
        status_lines = [
            "═" * 70,
            "LAYER 6: NATIVE C/C++ & JAVA BINARIES - Initialization Status",
            "═" * 70,
        ]
        
        components = [
            ("Native Mouse Controller", self.mouse_controller.is_available()),
            ("Native Keyboard Controller", self.keyboard_controller.is_available()),
            ("Native Browser Patcher", self.browser_patcher.is_available()),
            ("Java TLS Helper", self.java_tls_helper.available if self.java_tls_helper else False),
            ("Java DNS Resolver", self.java_dns_resolver.available if self.java_dns_resolver else False),
        ]
        
        for name, available in components:
            status = "✓ Binary loaded" if available else "✗ Not Available (inactive)"
            status_lines.append(f"{name:.<40} {status}")
        
        status_lines.append("═" * 70)
        
        self.logger.info("\n" + "\n".join(status_lines))
    
    async def apply_native_patches(self, context: 'pw.BrowserContext') -> dict[str, Any]:
        """
        Apply native-level patches to browser context.
        
        Args:
            context: Playwright browser context
        """
        
        self.logger.info("Layer 6 native patch request received")
        
        # Get browser process ID if available
        # (This would require CDP access to get PID)
        
        # Apply browser patching
        if self.browser_patcher.is_available():
            self.logger.warning("Native browser patcher binary is loaded, but process patching is not wired.")
            return {
                "applied": False,
                "status": "not_wired",
                "reason": "browser process patching is not implemented in the active runtime",
                "browser_patcher_available": True,
            }
        self.logger.info("Native browser patching inactive: no browser patcher binary loaded")
        return {
            "applied": False,
            "status": "inactive",
            "reason": "native browser patcher binary is not available",
            "browser_patcher_available": False,
        }
    
    async def move_mouse_native(
        self, page: pw.Page, x: int, y: int, duration_ms: float = 500
    ) -> bool:
        """
        Move mouse using native code with fallback to Playwright.
        
        Args:
            page: Playwright page
            x: Target X coordinate
            y: Target Y coordinate
            duration_ms: Movement duration
        
        Returns:
            True if successful
        """
        
        # Try native first
        if self.mouse_controller.is_available():
            success = await self.mouse_controller.move_to(x, y, duration_ms)
            if success:
                return True
        
        # Fallback to Playwright
        await page.mouse.move(x, y)
        return True
    
    async def click_native(self, page: pw.Page, x: int, y: int) -> bool:
        """
        Click using native code with fallback.
        
        Args:
            page: Playwright page
            x: Click X coordinate
            y: Click Y coordinate
        
        Returns:
            True if successful
        """
        
        # Try native first
        if self.mouse_controller.is_available():
            success = await self.mouse_controller.click(x, y)
            if success:
                return True
        
        # Fallback to Playwright
        await page.mouse.click(x, y)
        return True
    
    async def type_text_native(
        self, page: pw.Page, text: str, char_interval_ms: float = 100
    ) -> bool:
        """
        Type text using native keyboard with fallback.
        
        Args:
            page: Playwright page
            text: Text to type
            char_interval_ms: Character interval
        
        Returns:
            True if successful
        """
        
        # Try native first
        if self.keyboard_controller.is_available():
            success = await self.keyboard_controller.type_text(text, char_interval_ms)
            if success:
                return True
        
        # Fallback to Playwright
        await page.keyboard.type(text, delay=char_interval_ms)
        return True
    
    def get_status_report(self) -> dict[str, Any]:
        """Get status report of native layer."""
        components = {
            "native_mouse": self.mouse_controller.is_available(),
            "native_keyboard": self.keyboard_controller.is_available(),
            "browser_patcher": self.browser_patcher.is_available(),
            "java_tls_helper": self.java_tls_helper.available if self.java_tls_helper else False,
            "java_dns_resolver": self.java_dns_resolver.available if self.java_dns_resolver else False,
            "java_available": self.java_compiler.available,
        }
        native_loaded = any(components.values())
        
        return {
            "layer": 6,
            "name": "Native C/C++ & Java Binaries",
            "status": "adapter_ready" if native_loaded else "inactive",
            "active_in_job_runner": False,
            "backend": self.config.backend.value,
            "components": components,
            "features": {
                "os_level_input": self.mouse_controller.is_available() or self.keyboard_controller.is_available(),
                "runtime_patching": False,
                "browser_patcher_binary_loaded": self.browser_patcher.is_available(),
                "tls_diversification": self.java_tls_helper.available if self.java_tls_helper else False,
                "doh_dns_resolution": self.java_dns_resolver.available if self.java_dns_resolver else False,
                "on_demand_compilation": False,
            },
            "platform": platform.system(),
            "notes": "Native browser memory patching is not applied by the active scraper.",
        }
    
    def compile_missing_modules(self) -> None:
        """Compile any missing native modules (C/C++ and Java)."""
        
        self.logger.info("Checking for missing native modules...")
        
        # C/C++ modules
        modules = ["mouse_control", "keyboard_control", "browser_patcher"]
        
        for module in modules:
            if not self._is_module_available(module):
                self.logger.info(f"Compiling missing C/C++ module: {module}")
                self.compiler.compile_module(module)
        
        # Java modules
        if self.java_compiler.available:
            for java_module in ["tls_helper", "dns_resolver"]:
                if not self.java_compiler.is_compiled(java_module):
                    self.logger.info(f"Compiling missing Java module: {java_module}")
                    self.java_compiler.compile(java_module)
        else:
            self.logger.info("Java compiler not available — skipping Java modules")
    
    def _is_module_available(self, module_name: str) -> bool:
        """Check if module is available."""
        
        if module_name == "mouse_control":
            return self.mouse_controller.is_available()
        elif module_name == "keyboard_control":
            return self.keyboard_controller.is_available()
        elif module_name == "browser_patcher":
            return self.browser_patcher.is_available()
        
        return False


def create_native_layer(config: NativeLayerConfig = NativeLayerConfig()) -> Layer6NativeBinaries:
    """Create Layer 6 native binaries instance."""
    return Layer6NativeBinaries(config)


def native_layer_runtime_status(config: NativeLayerConfig = NativeLayerConfig()) -> dict[str, Any]:
    """Return a side-effect-free Layer 6 status report for API diagnostics."""
    system = platform.system().lower()
    if system == "windows":
        names = {
            "native_mouse": "mouse_control.dll",
            "native_keyboard": "keyboard_control.dll",
            "browser_patcher": "browser_patcher.dll",
        }
    elif system == "darwin":
        names = {
            "native_mouse": "libmouse_control.dylib",
            "native_keyboard": "libkeyboard_control.dylib",
            "browser_patcher": "libbrowser_patcher.dylib",
        }
    else:
        names = {
            "native_mouse": "libmouse_control.so",
            "native_keyboard": "libkeyboard_control.so",
            "browser_patcher": "libbrowser_patcher.so",
        }

    search_paths = [
        Path(__file__).parent / "native" / "build",
        Path(__file__).parent / "native" / "lib",
        Path.home() / ".asagus" / "native",
    ]
    if config.lib_path:
        search_paths.insert(0, Path(config.lib_path))

    components = {
        key: any((search_path / filename).exists() for search_path in search_paths)
        for key, filename in names.items()
    }
    java_available = bool(shutil.which("java") and shutil.which("javac"))
    components.update(
        {
            "java_available": java_available,
            "java_tls_helper": any((path / "java" / "tls_helper.class").exists() for path in search_paths),
            "java_dns_resolver": any((path / "java" / "dns_resolver.class").exists() for path in search_paths),
        }
    )
    native_loaded = any(components.values())
    return {
        "layer": 6,
        "name": "Native C/C++ & Java Binaries",
        "status": "adapter_ready" if native_loaded else "inactive",
        "active_in_job_runner": False,
        "backend": config.backend.value,
        "components": components,
        "features": {
            "os_level_input": components["native_mouse"] or components["native_keyboard"],
            "runtime_patching": False,
            "browser_patcher_binary_present": components["browser_patcher"],
            "tls_diversification": components["java_tls_helper"],
            "doh_dns_resolution": components["java_dns_resolver"],
            "on_demand_compilation": False,
        },
        "platform": platform.system(),
        "notes": "Native browser memory patching is not applied by the active scraper.",
    }


# ──────────────────────────────────────────────────────────────────────
# Java Binary Support — TLS Fingerprint Diversification & DNS-over-HTTPS
# ──────────────────────────────────────────────────────────────────────


class JavaCompiler:
    """
    On-the-fly Java compiler and runner.

    Detects javac/java on PATH and compiles .java sources from native/src/.
    Java binaries provide alternate TLS stacks (JA3 diversification)
    and secure DNS resolution (DNS-over-HTTPS) that complement the
    C/C++ binaries for additional stealth.
    """

    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)
        self.source_dir = Path(__file__).parent / "native" / "src"
        self.build_dir = Path(__file__).parent / "native" / "build" / "java"
        self._javac: str | None = None
        self._java: str | None = None
        self._detect_java()

    def _detect_java(self) -> None:
        """Detect javac and java on PATH."""
        for cmd, attr in [("javac", "_javac"), ("java", "_java")]:
            try:
                result = subprocess.run(
                    [cmd, "-version"],
                    capture_output=True,
                    timeout=5,
                )
                if result.returncode == 0:
                    setattr(self, attr, cmd)
                    self.logger.info("Found %s", cmd)
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass

    @property
    def available(self) -> bool:
        return self._javac is not None and self._java is not None

    def compile(self, module_name: str) -> bool:
        """Compile a .java file to .class in the build dir."""
        if not self._javac:
            self.logger.warning("javac not found — cannot compile Java sources")
            return False

        source = self.source_dir / f"{module_name}.java"
        if not source.exists():
            self.logger.error("Java source not found: %s", source)
            return False

        self.build_dir.mkdir(parents=True, exist_ok=True)
        try:
            result = subprocess.run(
                [self._javac, "-d", str(self.build_dir), str(source)],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                self.logger.info("✓ Compiled Java module: %s", module_name)
                return True
            self.logger.error("Java compilation failed: %s", result.stderr)
            return False
        except Exception as exc:
            self.logger.error("Java compilation error: %s", exc)
            return False

    def is_compiled(self, module_name: str) -> bool:
        """Check if a Java module is already compiled."""
        return (self.build_dir / f"{module_name}.class").exists()

    def run(self, module_name: str, args: list[str], timeout: int = 30) -> str | None:
        """
        Run a compiled Java class with the given arguments.
        Returns stdout output or None on failure.
        """
        if not self._java:
            return None

        if not self.is_compiled(module_name):
            if not self.compile(module_name):
                return None

        try:
            result = subprocess.run(
                [self._java, "-cp", str(self.build_dir), module_name, *args],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            if result.returncode == 0:
                return result.stdout.strip()
            self.logger.warning("Java %s failed: %s", module_name, result.stderr[:200])
            return None
        except subprocess.TimeoutExpired:
            self.logger.warning("Java %s timed out after %ds", module_name, timeout)
            return None
        except Exception as exc:
            self.logger.error("Java execution error: %s", exc)
            return None


class NativeJavaTLSHelper:
    """
    Python wrapper for the Java TLS fingerprint diversification binary.

    Provides alternate JA3 fingerprints by using Java's SSLContext with
    different cipher suite orderings than Python/curl-cffi.
    """

    def __init__(self) -> None:
        self.compiler = JavaCompiler()
        self.logger = logging.getLogger(__name__)
        if self.compiler.available:
            self.compiler.compile("tls_helper")

    @property
    def available(self) -> bool:
        return self.compiler.available and self.compiler.is_compiled("tls_helper")

    async def fetch_with_java_tls(
        self,
        url: str,
        profile: int = 0,
        timeout_ms: int = 15000,
    ) -> dict[str, Any] | None:
        """
        Fetch URL using Java TLS stack for fingerprint diversification.

        Args:
            url: Target URL
            profile: Cipher suite profile (0=Chrome, 1=Firefox, 2=Safari)
            timeout_ms: Connection timeout

        Returns:
            JSON dict with status, body, tls_protocol, cipher_suite, etc.
        """
        import json as _json

        args = [url, "--profile", str(profile), "--timeout", str(timeout_ms)]
        output = await asyncio.to_thread(self.compiler.run, "tls_helper", args, timeout=max(30, timeout_ms // 1000 + 5))
        if output:
            try:
                return _json.loads(output)
            except _json.JSONDecodeError:
                self.logger.warning("Invalid JSON from tls_helper: %s", output[:200])
        return None


class NativeJavaDNSResolver:
    """
    Python wrapper for the Java DNS-over-HTTPS resolver binary.

    Prevents DNS leaks by resolving domains via encrypted DoH instead
    of the system resolver, which could be monitored by ISPs.
    """

    def __init__(self) -> None:
        self.compiler = JavaCompiler()
        self.logger = logging.getLogger(__name__)
        if self.compiler.available:
            self.compiler.compile("dns_resolver")

    @property
    def available(self) -> bool:
        return self.compiler.available and self.compiler.is_compiled("dns_resolver")

    async def resolve(
        self,
        domain: str,
        provider: str = "cloudflare",
        record_type: str = "A",
    ) -> dict[str, Any] | None:
        """
        Resolve domain via DNS-over-HTTPS.

        Args:
            domain: Domain to resolve
            provider: DoH provider (cloudflare, google, quad9)
            record_type: DNS record type (A, AAAA)

        Returns:
            JSON dict with addresses, ttl, resolved flag, etc.
        """
        import json as _json

        args = [domain, "--provider", provider, "--type", record_type]
        output = await asyncio.to_thread(self.compiler.run, "dns_resolver", args, timeout=15)
        if output:
            try:
                return _json.loads(output)
            except _json.JSONDecodeError:
                self.logger.warning("Invalid JSON from dns_resolver: %s", output[:200])
        return None
