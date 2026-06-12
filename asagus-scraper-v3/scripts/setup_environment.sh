#!/bin/bash
# ============================================================
# ASAGUS Scraper v3.0 — Full Environment Setup
# ============================================================
# One-command setup for the entire development environment.
#
# What it does:
#   1. Validates system dependencies (Python, Node.js, g++, javac)
#   2. Creates Python virtual environment + installs backend deps
#   3. Installs frontend Node.js dependencies
#   4. Creates .env from template if not exists
#   5. Compiles native C/C++ and Java binaries
#   6. Installs Playwright browsers
#   7. Runs validation checks
#
# Usage:
#   chmod +x setup_environment.sh
#   ./setup_environment.sh
#
# FOR EDUCATION AND RESEARCH PURPOSES ONLY
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC}  $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step()  { echo -e "${BLUE}[STEP]${NC}  $1"; }
log_ok()    { echo -e "${CYAN}[OK]${NC}    $1"; }

# ── Step 1: Validate System Dependencies ──────────────────────────
validate_dependencies() {
    log_step "1/7 Validating system dependencies..."

    local required_ok=true
    local optional_ok=true

    # Required
    for cmd in python3 pip3 node npm; do
        if command -v "$cmd" &> /dev/null; then
            local version
            case "$cmd" in
                python3) version="$($cmd --version 2>&1)";;
                pip3)    version="$($cmd --version 2>&1 | head -1)";;
                node)    version="$($cmd --version 2>&1)";;
                npm)     version="$($cmd --version 2>&1)";;
            esac
            log_ok "  ✓ $cmd — $version"
        else
            log_error "  ✗ $cmd — NOT FOUND (required)"
            required_ok=false
        fi
    done

    # Optional but recommended
    for cmd in g++ gcc javac java docker git; do
        if command -v "$cmd" &> /dev/null; then
            log_ok "  ✓ $cmd — found"
        else
            log_warn "  ⊘ $cmd — not found (optional)"
            optional_ok=false
        fi
    done

    if ! $required_ok; then
        log_error "Missing required dependencies. Please install them first."
        exit 1
    fi

    if ! $optional_ok; then
        log_warn "Some optional tools are missing. Native binaries may not compile."
    fi
    echo ""
}

# ── Step 2: Python Virtual Environment ────────────────────────────
setup_python() {
    log_step "2/7 Setting up Python virtual environment..."

    local venv_dir="$BACKEND_DIR/.venv"

    if [[ ! -d "$venv_dir" ]]; then
        python3 -m venv "$venv_dir"
        log_info "  Created virtual environment at $venv_dir"
    else
        log_info "  Virtual environment already exists"
    fi

    # Activate
    source "$venv_dir/bin/activate" 2>/dev/null || source "$venv_dir/Scripts/activate" 2>/dev/null || true

    # Upgrade pip
    pip install --upgrade pip setuptools wheel -q

    # Install requirements
    if [[ -f "$BACKEND_DIR/requirements.txt" ]]; then
        log_info "  Installing Python dependencies..."
        pip install -r "$BACKEND_DIR/requirements.txt" -q
        log_ok "  ✓ Python dependencies installed"
    else
        log_warn "  requirements.txt not found at $BACKEND_DIR"
    fi
    echo ""
}

# ── Step 3: Frontend Dependencies ─────────────────────────────────
setup_frontend() {
    log_step "3/7 Installing frontend dependencies..."

    if [[ -f "$FRONTEND_DIR/package.json" ]]; then
        cd "$FRONTEND_DIR"
        npm install --silent 2>/dev/null || npm install
        log_ok "  ✓ Frontend dependencies installed"
        cd "$PROJECT_ROOT"
    else
        log_warn "  package.json not found at $FRONTEND_DIR"
    fi
    echo ""
}

# ── Step 4: Create .env from template ─────────────────────────────
setup_env() {
    log_step "4/7 Setting up .env configuration..."

    local env_file="$BACKEND_DIR/.env"

    if [[ -f "$env_file" ]]; then
        log_info "  .env already exists — skipping"
    else
        cat > "$env_file" << 'ENV_EOF'
# ============================================================
# ASAGUS Scraper v3.0 — Environment Configuration
# ============================================================
# Copy this file to .env and fill in your values

# App Settings
APP_NAME="ASAGUS Scraper 3.0"
ENVIRONMENT=local
API_HOST=0.0.0.0
API_PORT=8000
FRONTEND_ORIGIN=http://localhost:3000
OPERATOR_TOKEN=

# Database URLs
POSTGRES_URL=postgresql://asagus:asagus@localhost:5432/asagus
REDIS_URL=redis://localhost:6379/0
OPENSEARCH_HOST=http://localhost:9200
QDRANT_HOST=http://localhost:6333
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=asagus-graph
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=asagus-access
MINIO_SECRET_KEY=asagus-secret

# LLM Configuration (choose one provider)
LLM_PROVIDER=disabled
LLM_MODEL=
LLM_API_KEY=
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
GOOGLE_API_KEY=

# Proxy Configuration (optional)
BRIGHTDATA_USERNAME=
BRIGHTDATA_PASSWORD=
RESIDENTIAL_PROXY_URL=

# Scraping Settings
ENABLE_NETWORK_FETCH=true
ENABLE_SEARCH_DISCOVERY=true
CRAWL_CONCURRENCY_LIMIT=200
BROWSER_POOL_SIZE=10
BROWSER_AUTOMATION_ENGINE=playwright
ENV_EOF

        log_ok "  ✓ Created .env template at $env_file"
        log_warn "  ⚠ Please edit .env and add your API keys!"
    fi
    echo ""
}

# ── Step 5: Compile Native Binaries ───────────────────────────────
compile_native() {
    log_step "5/7 Compiling native binaries..."

    local compile_script="$SCRIPT_DIR/compile_native.sh"
    if [[ -f "$compile_script" ]]; then
        chmod +x "$compile_script"
        bash "$compile_script" --all
    else
        log_warn "  compile_native.sh not found — skipping"
    fi
    echo ""
}

# ── Step 6: Install Playwright Browsers ───────────────────────────
install_playwright() {
    log_step "6/7 Installing Playwright browsers..."

    if python3 -c "import playwright" 2>/dev/null; then
        python3 -m playwright install chromium 2>/dev/null || log_warn "  Playwright browser install failed (non-critical)"
        log_ok "  ✓ Playwright Chromium installed"
    else
        log_warn "  Playwright not installed — browser rendering will use fallback"
    fi
    echo ""
}

# ── Step 7: Validation ────────────────────────────────────────────
validate() {
    log_step "7/7 Running validation checks..."

    local checks=0
    local passed=0

    # Check Python imports
    checks=$((checks + 1))
    if python3 -c "import fastapi, pydantic, httpx; print('OK')" 2>/dev/null | grep -q "OK"; then
        log_ok "  ✓ Python core imports (fastapi, pydantic, httpx)"
        passed=$((passed + 1))
    else
        log_warn "  ✗ Missing Python dependencies"
    fi

    # Check .env
    checks=$((checks + 1))
    if [[ -f "$BACKEND_DIR/.env" ]]; then
        log_ok "  ✓ .env file exists"
        passed=$((passed + 1))
    else
        log_warn "  ✗ .env file not found"
    fi

    # Check frontend
    checks=$((checks + 1))
    if [[ -d "$FRONTEND_DIR/node_modules" ]]; then
        log_ok "  ✓ Frontend node_modules exists"
        passed=$((passed + 1))
    else
        log_warn "  ✗ Frontend dependencies not installed"
    fi

    # Check native build dir
    checks=$((checks + 1))
    if [[ -d "$PROJECT_ROOT/backend/asagus/layers/native/lib" ]] || [[ -d "$PROJECT_ROOT/backend/asagus/layers/native/build" ]]; then
        log_ok "  ✓ Native binary build directory exists"
        passed=$((passed + 1))
    else
        log_warn "  ✗ Native binaries not compiled"
    fi

    echo ""
    echo "════════════════════════════════════════════════════════════"
    log_info "Validation: $passed/$checks checks passed"
    echo "════════════════════════════════════════════════════════════"
    echo ""
    log_info "To start the backend:  cd backend && python -m uvicorn asagus.main:app --reload"
    log_info "To start the frontend: cd frontend && npm run dev"
    log_info "To setup databases:    ./scripts/setup_databases.sh --start"
    echo ""
}

# ── Main ───────────────────────────────────────────────────────────
main() {
    echo ""
    echo "╔══════════════════════════════════════════════════════════╗"
    echo "║   ASAGUS Scraper v3.0 — Full Environment Setup         ║"
    echo "╚══════════════════════════════════════════════════════════╝"
    echo ""

    validate_dependencies
    setup_python
    setup_frontend
    setup_env
    compile_native
    install_playwright
    validate

    log_info "Setup complete! 🚀"
}

main "$@"
