#!/bin/bash
# ============================================================
# ASAGUS Scraper v3.0 — Native Binary Compilation Script
# ============================================================
# Compiles C/C++ and Java binaries for Layer 6 anti-detection.
#
# Binaries:
#   C/C++:  mouse_control.cpp, keyboard_control.cpp, browser_patcher.c
#   Java:   tls_helper.java, dns_resolver.java
#
# Usage:
#   chmod +x compile_native.sh
#   ./compile_native.sh [--all|--cpp|--java|--clean|--test]
#
# FOR EDUCATION AND RESEARCH PURPOSES ONLY
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
NATIVE_DIR="$PROJECT_ROOT/backend/asagus/layers/native"
SRC_DIR="$NATIVE_DIR/src"
BUILD_DIR="$NATIVE_DIR/build"
LIB_DIR="$NATIVE_DIR/lib"
JAVA_BUILD_DIR="$BUILD_DIR/java"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC}  $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step()  { echo -e "${BLUE}[STEP]${NC}  $1"; }
log_ok()    { echo -e "${CYAN}[OK]${NC}    $1"; }

# ── Platform Detection ─────────────────────────────────────────────
detect_platform() {
    local os_name
    os_name="$(uname -s)"
    case "$os_name" in
        Linux*)   PLATFORM="linux";;
        Darwin*)  PLATFORM="macos";;
        CYGWIN*|MINGW*|MSYS*)  PLATFORM="windows";;
        *)        PLATFORM="unknown";;
    esac
    log_info "Platform: $PLATFORM ($(uname -m))"
}

# ── Compiler Detection ─────────────────────────────────────────────
detect_cpp_compiler() {
    CXX=""
    CC=""

    for compiler in g++ clang++ c++; do
        if command -v "$compiler" &> /dev/null; then
            CXX="$compiler"
            log_info "C++ compiler: $CXX ($(${CXX} --version 2>&1 | head -1))"
            break
        fi
    done

    for compiler in gcc clang cc; do
        if command -v "$compiler" &> /dev/null; then
            CC="$compiler"
            log_info "C compiler: $CC"
            break
        fi
    done

    if [[ -z "$CXX" && -z "$CC" ]]; then
        log_error "No C/C++ compiler found!"
        log_info "Install with:"
        case "$PLATFORM" in
            linux)  echo "  sudo apt install build-essential  # Debian/Ubuntu"
                    echo "  sudo dnf install gcc-c++           # Fedora";;
            macos)  echo "  xcode-select --install";;
            windows) echo "  Install MinGW-w64 or Visual Studio Build Tools";;
        esac
        return 1
    fi
    return 0
}

detect_java_compiler() {
    JAVAC=""
    JAVA=""

    if command -v javac &> /dev/null; then
        JAVAC="javac"
        log_info "Java compiler: javac ($(javac -version 2>&1))"
    fi

    if command -v java &> /dev/null; then
        JAVA="java"
        log_info "Java runtime: java ($(java -version 2>&1 | head -1))"
    fi

    if [[ -z "$JAVAC" ]]; then
        log_warn "javac not found — Java binaries will be skipped"
        log_info "Install JDK 17+ from: https://adoptium.net/"
        return 1
    fi
    return 0
}

# ── C/C++ Compilation ──────────────────────────────────────────────
compile_cpp() {
    log_step "Compiling C/C++ native binaries..."

    mkdir -p "$BUILD_DIR" "$LIB_DIR"

    local cxx_flags="-O3 -Wall -Wextra"
    local c_flags="-O3 -Wall -Wextra"
    local shared_flag="-shared -fPIC"
    local lib_ext=".so"

    case "$PLATFORM" in
        macos)
            lib_ext=".dylib"
            shared_flag="-dynamiclib -fPIC"
            cxx_flags="$cxx_flags -std=c++17"
            ;;
        windows)
            lib_ext=".dll"
            shared_flag="-shared"
            cxx_flags="$cxx_flags -std=c++17"
            ;;
        *)
            cxx_flags="$cxx_flags -std=c++17"
            ;;
    esac

    # Add platform-specific link libraries
    local platform_libs=""
    case "$PLATFORM" in
        linux)   platform_libs="-lX11 -lXtst";;
        macos)   platform_libs="-framework ApplicationServices -framework Carbon";;
        windows) platform_libs="-luser32 -lgdi32";;
    esac

    local compiled=0
    local failed=0

    # ── mouse_control.cpp ──
    if [[ -n "$CXX" && -f "$SRC_DIR/mouse_control.cpp" ]]; then
        log_step "  Compiling mouse_control.cpp..."
        if $CXX $cxx_flags $shared_flag \
            "$SRC_DIR/mouse_control.cpp" \
            -o "$LIB_DIR/libmouse_control${lib_ext}" \
            $platform_libs 2>/dev/null; then
            log_ok "  ✓ libmouse_control${lib_ext}"
            compiled=$((compiled + 1))
        else
            log_warn "  ✗ mouse_control.cpp failed (missing platform headers?)"
            failed=$((failed + 1))
        fi
    fi

    # ── keyboard_control.cpp ──
    if [[ -n "$CXX" && -f "$SRC_DIR/keyboard_control.cpp" ]]; then
        log_step "  Compiling keyboard_control.cpp..."
        if $CXX $cxx_flags $shared_flag \
            "$SRC_DIR/keyboard_control.cpp" \
            -o "$LIB_DIR/libkeyboard_control${lib_ext}" \
            $platform_libs 2>/dev/null; then
            log_ok "  ✓ libkeyboard_control${lib_ext}"
            compiled=$((compiled + 1))
        else
            log_warn "  ✗ keyboard_control.cpp failed (missing platform headers?)"
            failed=$((failed + 1))
        fi
    fi

    # ── browser_patcher.c ──
    if [[ -n "$CC" && -f "$SRC_DIR/browser_patcher.c" ]]; then
        log_step "  Compiling browser_patcher.c..."
        if $CC $c_flags $shared_flag \
            "$SRC_DIR/browser_patcher.c" \
            -o "$LIB_DIR/libbrowser_patcher${lib_ext}" \
            2>/dev/null; then
            log_ok "  ✓ libbrowser_patcher${lib_ext}"
            compiled=$((compiled + 1))
        else
            log_warn "  ✗ browser_patcher.c failed"
            failed=$((failed + 1))
        fi
    fi

    echo ""
    log_info "C/C++ compilation: $compiled succeeded, $failed failed"
}

# ── Java Compilation ───────────────────────────────────────────────
compile_java() {
    log_step "Compiling Java binaries..."

    mkdir -p "$JAVA_BUILD_DIR"

    local compiled=0
    local failed=0

    local java_sources=("tls_helper" "dns_resolver")

    for source in "${java_sources[@]}"; do
        local source_file="$SRC_DIR/${source}.java"
        if [[ ! -f "$source_file" ]]; then
            log_warn "  ✗ ${source}.java not found"
            failed=$((failed + 1))
            continue
        fi

        log_step "  Compiling ${source}.java..."
        if $JAVAC -d "$JAVA_BUILD_DIR" "$source_file" 2>/dev/null; then
            log_ok "  ✓ ${source}.class"
            compiled=$((compiled + 1))
        else
            log_warn "  ✗ ${source}.java failed"
            failed=$((failed + 1))
        fi
    done

    echo ""
    log_info "Java compilation: $compiled succeeded, $failed failed"
}

# ── Smoke Tests ────────────────────────────────────────────────────
run_tests() {
    log_step "Running smoke tests..."
    local passed=0
    local total=0

    # Test C/C++ library existence
    for lib in libmouse_control libbrowser_patcher libkeyboard_control; do
        total=$((total + 1))
        local found=false
        for ext in .so .dylib .dll; do
            if [[ -f "$LIB_DIR/${lib}${ext}" ]]; then
                log_ok "  ✓ $lib — found ($(du -h "$LIB_DIR/${lib}${ext}" | cut -f1))"
                passed=$((passed + 1))
                found=true
                break
            fi
        done
        if ! $found; then
            log_warn "  ✗ $lib — not found"
        fi
    done

    # Test Java class existence
    for class in tls_helper dns_resolver; do
        total=$((total + 1))
        if [[ -f "$JAVA_BUILD_DIR/${class}.class" ]]; then
            log_ok "  ✓ ${class}.class — found"
            passed=$((passed + 1))
        else
            log_warn "  ✗ ${class}.class — not found"
        fi
    done

    # Test Java execution if available
    if [[ -n "${JAVA:-}" && -f "$JAVA_BUILD_DIR/tls_helper.class" ]]; then
        total=$((total + 1))
        if $JAVA -cp "$JAVA_BUILD_DIR" tls_helper --help 2>/dev/null | grep -q "TLS Helper"; then
            log_ok "  ✓ tls_helper --help — works"
            passed=$((passed + 1))
        else
            log_warn "  ✗ tls_helper --help — failed"
        fi
    fi

    if [[ -n "${JAVA:-}" && -f "$JAVA_BUILD_DIR/dns_resolver.class" ]]; then
        total=$((total + 1))
        if $JAVA -cp "$JAVA_BUILD_DIR" dns_resolver --help 2>/dev/null | grep -q "DNS"; then
            log_ok "  ✓ dns_resolver --help — works"
            passed=$((passed + 1))
        else
            log_warn "  ✗ dns_resolver --help — failed"
        fi
    fi

    echo ""
    log_info "Tests: $passed/$total passed"
}

# ── Clean ──────────────────────────────────────────────────────────
clean() {
    log_step "Cleaning build artifacts..."
    rm -rf "$BUILD_DIR" "$LIB_DIR"
    mkdir -p "$BUILD_DIR" "$LIB_DIR"
    log_info "Clean complete."
}

# ── Main ───────────────────────────────────────────────────────────
main() {
    local action="${1:---all}"

    echo ""
    echo "════════════════════════════════════════════════════════════"
    echo "  ASAGUS Scraper v3.0 — Native Binary Compilation"
    echo "════════════════════════════════════════════════════════════"
    echo ""

    detect_platform

    case "$action" in
        --all|-a)
            detect_cpp_compiler && compile_cpp || log_warn "C/C++ skipped"
            detect_java_compiler && compile_java || log_warn "Java skipped"
            echo ""
            run_tests
            ;;
        --cpp|-c)
            detect_cpp_compiler && compile_cpp
            ;;
        --java|-j)
            detect_java_compiler && compile_java
            ;;
        --test|-t)
            detect_platform
            detect_java_compiler || true
            run_tests
            ;;
        --clean)
            clean
            ;;
        --help|-h)
            echo "Usage: $0 [--all|--cpp|--java|--test|--clean|--help]"
            echo ""
            echo "Options:"
            echo "  --all, -a    Compile everything + run tests (default)"
            echo "  --cpp, -c    Compile C/C++ binaries only"
            echo "  --java, -j   Compile Java binaries only"
            echo "  --test, -t   Run smoke tests only"
            echo "  --clean      Remove all build artifacts"
            echo "  --help, -h   Show this help"
            ;;
        *)
            log_error "Unknown option: $action"
            echo "Use --help for usage information."
            exit 1
            ;;
    esac

    echo ""
    log_info "Done!"
}

main "$@"
