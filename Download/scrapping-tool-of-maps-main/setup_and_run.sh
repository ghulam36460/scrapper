#!/usr/bin/env bash
# =============================================================
# Google Maps Lead Scraper — Setup & Run Script
# =============================================================
# Usage:
#   chmod +x setup_and_run.sh
#   ./setup_and_run.sh              # setup + run on port 5001
#   ./setup_and_run.sh --setup-only # only install, don't run
#   ./setup_and_run.sh --run-only   # skip install, just run
#   APP_PORT=8080 ./setup_and_run.sh  # custom port
# =============================================================

set -euo pipefail

# ---------- Configurable defaults ----------------------------
APP_PORT="${APP_PORT:-5001}"
APP_HOST="${APP_HOST:-127.0.0.1}"
VENV_DIR=".venv"
PYTHON_MIN_VERSION="3.9"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# -------------------------------------------------------------

GREEN="\033[0;32m"
YELLOW="\033[1;33m"
RED="\033[0;31m"
CYAN="\033[0;36m"
RESET="\033[0m"

info()    { echo -e "${CYAN}[INFO]${RESET}  $*"; }
success() { echo -e "${GREEN}[OK]${RESET}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${RESET}  $*"; }
error()   { echo -e "${RED}[ERROR]${RESET} $*" >&2; exit 1; }

# ---------- Parse flags --------------------------------------
SETUP=true
RUN=true

for arg in "$@"; do
  case "$arg" in
    --setup-only) RUN=false ;;
    --run-only)   SETUP=false ;;
    --help|-h)
      echo "Usage: $0 [--setup-only | --run-only]"
      echo "  --setup-only   Install dependencies and browser, then exit."
      echo "  --run-only     Skip install, launch the server directly."
      echo ""
      echo "Environment vars:"
      echo "  APP_PORT=5001   Port to listen on (default: 5001)"
      echo "  APP_HOST=127.0.0.1  Host to bind (default: 127.0.0.1)"
      exit 0
      ;;
    *) warn "Unknown argument: $arg" ;;
  esac
done

# ---------- Banner -------------------------------------------
echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════════╗${RESET}"
echo -e "${CYAN}║   Google Maps Lead Scraper — Setup & Run           ║${RESET}"
echo -e "${CYAN}╚══════════════════════════════════════════════════════╝${RESET}"
echo ""

cd "$SCRIPT_DIR"

# =============================================================
# SETUP PHASE
# =============================================================
if [ "$SETUP" = true ]; then

  # ---- Locate Python -------------------------------------------
  info "Checking Python installation..."
  PYTHON_BIN=""
  for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
      ver=$("$cmd" -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>/dev/null || echo "0.0")
      major=$(echo "$ver" | cut -d. -f1)
      minor=$(echo "$ver" | cut -d. -f2)
      req_major=$(echo "$PYTHON_MIN_VERSION" | cut -d. -f1)
      req_minor=$(echo "$PYTHON_MIN_VERSION" | cut -d. -f2)
      if [ "$major" -gt "$req_major" ] || ([ "$major" -eq "$req_major" ] && [ "$minor" -ge "$req_minor" ]); then
        PYTHON_BIN="$cmd"
        success "Found Python $ver at $(command -v $cmd)"
        break
      fi
    fi
  done

  if [ -z "$PYTHON_BIN" ]; then
    error "Python $PYTHON_MIN_VERSION or higher not found. Please install Python first.\n  Ubuntu/Debian: sudo apt install python3\n  macOS:         brew install python3"
  fi

  # ---- Create virtual environment ------------------------------
  if [ ! -d "$VENV_DIR" ]; then
    info "Creating virtual environment in ./$VENV_DIR ..."
    "$PYTHON_BIN" -m venv "$VENV_DIR"
    success "Virtual environment created."
  else
    info "Virtual environment already exists — skipping creation."
  fi

  # ---- Activate venv ------------------------------------------
  if [ -f "$VENV_DIR/bin/activate" ]; then
    # shellcheck disable=SC1091
    source "$VENV_DIR/bin/activate"
  else
    error "Failed to find venv activation script."
  fi

  VENV_PYTHON="$SCRIPT_DIR/$VENV_DIR/bin/python"
  VENV_PIP="$SCRIPT_DIR/$VENV_DIR/bin/pip"

  # ---- Upgrade pip + setuptools --------------------------------
  info "Upgrading pip, setuptools, wheel..."
  "$VENV_PYTHON" -m pip install --upgrade pip setuptools wheel --quiet
  success "pip upgraded."

  # ---- Install requirements ------------------------------------
  info "Installing Python dependencies from requirements.txt..."
  "$VENV_PIP" install -r requirements.txt --upgrade --quiet
  success "Python dependencies installed."

  # ---- Install Playwright browsers ----------------------------
  info "Installing Playwright Chromium browser..."
  "$VENV_PYTHON" -m playwright install chromium
  success "Playwright Chromium installed."

  # ---- Install system deps for Playwright (Linux) -------------
  if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    info "Installing Playwright system dependencies (may need sudo)..."
    "$VENV_PYTHON" -m playwright install-deps chromium 2>/dev/null || \
      warn "playwright install-deps skipped (may need manual: sudo playwright install-deps chromium)"
  fi

  # ---- Create output directories if missing -------------------
  mkdir -p output/history/searches
  success "Output directories ready."

  echo ""
  success "═══ Setup complete! ═══"
  echo ""

fi  # end SETUP

# =============================================================
# RUN PHASE
# =============================================================
if [ "$RUN" = true ]; then

  # Activate venv if not already active
  if [ -z "${VIRTUAL_ENV:-}" ]; then
    if [ -f "$VENV_DIR/bin/activate" ]; then
      # shellcheck disable=SC1091
      source "$VENV_DIR/bin/activate"
    else
      error "Virtual environment not found. Run without --run-only first to set it up."
    fi
  fi

  VENV_PYTHON="$(cd "$SCRIPT_DIR" && pwd)/$VENV_DIR/bin/python"

  # Verify app.py exists
  if [ ! -f "backend/app.py" ]; then
    error "backend/app.py not found. Are you running from the project root?"
  fi

  echo ""
  echo -e "${GREEN}╔══════════════════════════════════════════════════════╗${RESET}"
  echo -e "${GREEN}║  Starting server on http://${APP_HOST}:${APP_PORT}         ║${RESET}"
  echo -e "${GREEN}║  Open this URL in your browser                        ║${RESET}"
  echo -e "${GREEN}║  Press Ctrl+C to stop                                 ║${RESET}"
  echo -e "${GREEN}╚══════════════════════════════════════════════════════╝${RESET}"
  echo ""

  cd backend
  APP_PORT="$APP_PORT" APP_HOST="$APP_HOST" "$VENV_PYTHON" app.py

fi
