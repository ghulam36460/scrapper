#!/bin/bash
# Build Script for Native Anti-Detection Libraries
# ================================================
# Automatically compiles all C/C++ modules with proper error handling

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  ASAGUS Native Layer Build Script                         ║${NC}"
echo -e "${BLUE}║  Building C/C++ Anti-Detection Binaries                   ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Detect platform
OS="$(uname -s)"
ARCH="$(uname -m)"

echo -e "${YELLOW}Platform:${NC} $OS ($ARCH)"
echo ""

# Check for compilers
check_compiler() {
    if command -v g++ &> /dev/null; then
        CXX="g++"
        echo -e "${GREEN}✓${NC} Found C++ compiler: g++ ($(g++ --version | head -n1))"
        return 0
    elif command -v clang++ &> /dev/null; then
        CXX="clang++"
        echo -e "${GREEN}✓${NC} Found C++ compiler: clang++ ($(clang++ --version | head -n1))"
        return 0
    else
        echo -e "${RED}✗${NC} No C++ compiler found!"
        return 1
    fi
}

check_linux_x11_deps() {
    if command -v pkg-config &> /dev/null && pkg-config --exists x11 xtst 2>/dev/null; then
        echo -e "${GREEN}✓${NC} X11 development headers found"
        return 0
    fi

    local dep_check_dir
    local dep_check_log
    dep_check_dir="$(mktemp -d)"
    dep_check_log="$dep_check_dir/x11_check.log"

    if printf '%s\n' \
        '#include <X11/Xlib.h>' \
        '#include <X11/extensions/XTest.h>' \
        'int main() { return 0; }' \
        | "$CXX" -x c++ - -o "$dep_check_dir/x11_check" -lX11 -lXtst >"$dep_check_log" 2>&1; then
        rm -rf "$dep_check_dir"
        if command -v pkg-config &> /dev/null; then
            echo -e "${GREEN}✓${NC} X11 development headers found (pkg-config metadata unavailable)"
        else
            echo -e "${GREEN}✓${NC} X11 development headers found (pkg-config not installed)"
        fi
        return 0
    fi

    rm -rf "$dep_check_dir"
    echo -e "${YELLOW}⚠${NC} X11 development headers not found"
    echo "  Install with: sudo apt install libx11-dev libxtst-dev"
    if ! command -v pkg-config &> /dev/null; then
        echo "  Optional dependency checker: sudo apt install pkg-config"
    fi
    echo "  Continuing anyway (may fail during compilation)..."
    return 1
}

if ! check_compiler; then
    echo ""
    echo -e "${YELLOW}Please install a C++ compiler:${NC}"
    case "$OS" in
        Linux)
            echo "  Ubuntu/Debian: sudo apt install build-essential"
            echo "  Fedora/RHEL:   sudo dnf install gcc-c++"
            echo "  Arch:          sudo pacman -S base-devel"
            ;;
        Darwin)
            echo "  macOS:         xcode-select --install"
            ;;
    esac
    exit 1
fi

# Check for platform-specific dependencies
echo ""
echo -e "${YELLOW}Checking dependencies...${NC}"

case "$OS" in
    Linux)
        check_linux_x11_deps || true
        ;;
    Darwin)
        echo -e "${GREEN}✓${NC} macOS frameworks available"
        ;;
esac

echo ""
echo -e "${YELLOW}Starting build...${NC}"
echo ""

# Try Makefile first
if [ -f "Makefile" ]; then
    echo -e "${BLUE}Building with Makefile...${NC}"
    if make all; then
        echo ""
        echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
        echo -e "${GREEN}║  ✓ Build Successful!                                       ║${NC}"
        echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
        echo ""
        echo "Libraries built:"
        ls -lh lib/ 2>/dev/null || echo "No libraries found"
        echo ""
        echo "To install system-wide:"
        echo "  make install"
        echo ""
        echo "To test libraries:"
        echo "  make test"
        exit 0
    else
        echo -e "${RED}✗ Makefile build failed${NC}"
        echo "Trying CMake..."
    fi
fi

# Try CMake as fallback
if command -v cmake &> /dev/null; then
    echo -e "${BLUE}Building with CMake...${NC}"
    mkdir -p build
    cd build
    
    if cmake .. -DCMAKE_BUILD_TYPE=Release && cmake --build .; then
        cd ..
        echo ""
        echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
        echo -e "${GREEN}║  ✓ Build Successful (CMake)!                               ║${NC}"
        echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
        exit 0
    else
        cd ..
        echo -e "${RED}✗ CMake build failed${NC}"
    fi
fi

# Manual compilation as last resort
echo ""
echo -e "${YELLOW}Attempting manual compilation...${NC}"

mkdir -p lib
mkdir -p build

# Platform-specific settings
case "$OS" in
    Linux)
        EXT="so"
        PREFIX="lib"
        LDFLAGS="-shared -lX11 -lXtst"
        ;;
    Darwin)
        EXT="dylib"
        PREFIX="lib"
        LDFLAGS="-shared -framework ApplicationServices -framework Carbon"
        ;;
    *)
        echo -e "${RED}✗ Unsupported platform: $OS${NC}"
        exit 1
        ;;
esac

# Compile each module
compile_module() {
    local name=$1
    local src=$2
    local compiler=$3
    
    echo -n "  Compiling $name... "
    
    if $compiler -std=c++17 -O3 -fPIC -march=native \
        "src/$src" -o "lib/${PREFIX}${name}.${EXT}" \
        $LDFLAGS 2>build/${name}_error.log; then
        echo -e "${GREEN}✓${NC}"
        return 0
    else
        echo -e "${RED}✗${NC}"
        echo "    Error log: build/${name}_error.log"
        return 1
    fi
}

SUCCESS=0

echo ""
compile_module "mouse_control" "mouse_control.cpp" "$CXX" && ((SUCCESS++))
compile_module "keyboard_control" "keyboard_control.cpp" "$CXX" && ((SUCCESS++))

# Browser patcher needs C compiler
if command -v gcc &> /dev/null; then
    CC="gcc"
elif command -v clang &> /dev/null; then
    CC="clang"
else
    CC="$CXX"
fi

if $CC -std=c11 -O3 -fPIC -march=native \
    "src/browser_patcher.c" -o "lib/${PREFIX}browser_patcher.${EXT}" \
    $LDFLAGS 2>build/browser_patcher_error.log; then
    echo -e "  Compiling browser_patcher... ${GREEN}✓${NC}"
    ((SUCCESS++))
else
    echo -e "  Compiling browser_patcher... ${RED}✗${NC}"
    echo "    Error log: build/browser_patcher_error.log"
fi

echo ""

if [ $SUCCESS -eq 3 ]; then
    echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║  ✓ All modules compiled successfully!                      ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo "Libraries built:"
    ls -lh lib/
    exit 0
elif [ $SUCCESS -gt 0 ]; then
    echo -e "${YELLOW}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${YELLOW}║  ⚠ Partial Success: $SUCCESS/3 modules compiled               ║${NC}"
    echo -e "${YELLOW}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo "Check error logs in build/ directory for details"
    exit 1
else
    echo -e "${RED}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${RED}║  ✗ Build Failed!                                           ║${NC}"
    echo -e "${RED}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo "Check error logs in build/ directory for details"
    exit 1
fi
