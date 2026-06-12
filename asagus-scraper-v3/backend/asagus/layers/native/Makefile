# Makefile for Native Anti-Detection Libraries
# ============================================
# Compiles C/C++ native modules for all platforms

# Detect platform
UNAME_S := $(shell uname -s)
ARCH := $(shell uname -m)

# Compiler settings
CXX := g++
CC := gcc
CXXFLAGS := -std=c++17 -O3 -Wall -fPIC -march=native
CFLAGS := -std=c11 -O3 -Wall -fPIC -march=native

# Platform-specific settings
ifeq ($(UNAME_S),Linux)
    PLATFORM := linux
    LIB_EXT := so
    LDFLAGS := -shared -lX11 -lXtst
    PREFIX := lib
endif

ifeq ($(UNAME_S),Darwin)
    PLATFORM := macos
    LIB_EXT := dylib
    LDFLAGS := -shared -framework ApplicationServices -framework Carbon -framework Cocoa
    PREFIX := lib
endif

ifeq ($(OS),Windows_NT)
    PLATFORM := windows
    LIB_EXT := dll
    LDFLAGS := -shared -lpsapi
    PREFIX := 
    CXX := cl
    CC := cl
endif

# Directories
SRC_DIR := src
BUILD_DIR := build
LIB_DIR := lib

# Targets
MOUSE_LIB := $(LIB_DIR)/$(PREFIX)mouse_control.$(LIB_EXT)
KEYBOARD_LIB := $(LIB_DIR)/$(PREFIX)keyboard_control.$(LIB_EXT)
BROWSER_LIB := $(LIB_DIR)/$(PREFIX)browser_patcher.$(LIB_EXT)

ALL_LIBS := $(MOUSE_LIB) $(KEYBOARD_LIB) $(BROWSER_LIB)

# Default target
.PHONY: all
all: setup $(ALL_LIBS)
	@echo ""
	@echo "✓ All native libraries compiled successfully for $(PLATFORM)!"
	@echo ""
	@echo "Libraries:"
	@ls -lh $(LIB_DIR)/

# Setup directories
.PHONY: setup
setup:
	@mkdir -p $(BUILD_DIR)
	@mkdir -p $(LIB_DIR)
	@echo "Building for platform: $(PLATFORM) ($(ARCH))"

# Mouse control library
$(MOUSE_LIB): $(SRC_DIR)/mouse_control.cpp
	@echo "Compiling mouse_control..."
	$(CXX) $(CXXFLAGS) $< -o $@ $(LDFLAGS)
	@echo "✓ Mouse control library built"

# Keyboard control library
$(KEYBOARD_LIB): $(SRC_DIR)/keyboard_control.cpp
	@echo "Compiling keyboard_control..."
	$(CXX) $(CXXFLAGS) $< -o $@ $(LDFLAGS)
	@echo "✓ Keyboard control library built"

# Browser patcher library
$(BROWSER_LIB): $(SRC_DIR)/browser_patcher.c
	@echo "Compiling browser_patcher..."
	$(CC) $(CFLAGS) $< -o $@ $(LDFLAGS)
	@echo "✓ Browser patcher library built"

# Clean build artifacts
.PHONY: clean
clean:
	@echo "Cleaning build artifacts..."
	rm -rf $(BUILD_DIR)/*
	rm -rf $(LIB_DIR)/*
	@echo "✓ Clean complete"

# Test libraries
.PHONY: test
test: all
	@echo ""
	@echo "Testing native libraries..."
	@echo ""
	@python3 -c "import ctypes; lib = ctypes.CDLL('$(MOUSE_LIB)'); lib.test_native_mouse()"
	@python3 -c "import ctypes; lib = ctypes.CDLL('$(KEYBOARD_LIB)'); lib.test_native_keyboard()"
	@python3 -c "import ctypes; lib = ctypes.CDLL('$(BROWSER_LIB)'); lib.test_browser_patcher()"

# Install to system
.PHONY: install
install: all
	@echo "Installing native libraries..."
	mkdir -p ~/.asagus/native
	cp $(LIB_DIR)/* ~/.asagus/native/
	@echo "✓ Libraries installed to ~/.asagus/native/"

# Show info
.PHONY: info
info:
	@echo "Native Build System Information"
	@echo "==============================="
	@echo "Platform: $(PLATFORM)"
	@echo "Architecture: $(ARCH)"
	@echo "C++ Compiler: $(CXX)"
	@echo "C Compiler: $(CC)"
	@echo "Library Extension: $(LIB_EXT)"
	@echo "Build Directory: $(BUILD_DIR)"
	@echo "Output Directory: $(LIB_DIR)"

# Help
.PHONY: help
help:
	@echo "Native Anti-Detection Libraries - Build System"
	@echo "=============================================="
	@echo ""
	@echo "Available targets:"
	@echo "  make all      - Build all native libraries (default)"
	@echo "  make clean    - Remove build artifacts"
	@echo "  make test     - Test compiled libraries"
	@echo "  make install  - Install libraries to ~/.asagus/native/"
	@echo "  make info     - Show build system information"
	@echo "  make help     - Show this help message"
	@echo ""
	@echo "Platform: $(PLATFORM)"
