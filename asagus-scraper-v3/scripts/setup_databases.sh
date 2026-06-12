#!/bin/bash
# ============================================================
# ASAGUS Scraper v3.0 — Database Infrastructure Setup
# ============================================================
# Sets up all required databases and services using Docker.
# Services: PostgreSQL, Redis, OpenSearch, Qdrant, Neo4j, MinIO
#
# Usage:
#   chmod +x setup_databases.sh
#   ./setup_databases.sh [--start|--stop|--status|--reset]
#
# FOR EDUCATION AND RESEARCH PURPOSES ONLY
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
COMPOSE_FILE="$SCRIPT_DIR/docker-compose.databases.yml"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info()  { echo -e "${GREEN}[INFO]${NC}  $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step()  { echo -e "${BLUE}[STEP]${NC}  $1"; }

# ── Generate docker-compose.databases.yml ──────────────────────────
generate_compose() {
    cat > "$COMPOSE_FILE" << 'COMPOSE_EOF'
version: "3.9"

services:
  # ── PostgreSQL (Primary + Secondary DB) ─────────────────────────
  postgres:
    image: postgres:16-alpine
    container_name: asagus-postgres
    restart: unless-stopped
    environment:
      POSTGRES_USER: asagus
      POSTGRES_PASSWORD: asagus
      POSTGRES_DB: asagus
    ports:
      - "5432:5432"
    volumes:
      - asagus_postgres_data:/var/lib/postgresql/data
      - ./init_postgres.sql:/docker-entrypoint-initdb.d/init.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U asagus"]
      interval: 10s
      timeout: 5s
      retries: 5

  # ── Redis (Caching + Rate Limiting) ─────────────────────────────
  redis:
    image: redis:7-alpine
    container_name: asagus-redis
    restart: unless-stopped
    ports:
      - "6379:6379"
    command: redis-server --maxmemory 512mb --maxmemory-policy allkeys-lru
    volumes:
      - asagus_redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  # ── OpenSearch (Full-Text Index) ────────────────────────────────
  opensearch:
    image: opensearchproject/opensearch:2.11.0
    container_name: asagus-opensearch
    restart: unless-stopped
    environment:
      - discovery.type=single-node
      - DISABLE_SECURITY_PLUGIN=true
      - OPENSEARCH_JAVA_OPTS=-Xms512m -Xmx512m
    ports:
      - "9200:9200"
      - "9600:9600"
    volumes:
      - asagus_opensearch_data:/usr/share/opensearch/data
    healthcheck:
      test: ["CMD-SHELL", "curl -s http://localhost:9200 | grep -q 'cluster_name'"]
      interval: 15s
      timeout: 10s
      retries: 5

  # ── Qdrant (Vector Search) ──────────────────────────────────────
  qdrant:
    image: qdrant/qdrant:v1.7.4
    container_name: asagus-qdrant
    restart: unless-stopped
    ports:
      - "6333:6333"
      - "6334:6334"
    volumes:
      - asagus_qdrant_data:/qdrant/storage
    healthcheck:
      test: ["CMD-SHELL", "curl -s http://localhost:6333/health | grep -q 'ok'"]
      interval: 10s
      timeout: 5s
      retries: 5

  # ── Neo4j (Graph Database) ──────────────────────────────────────
  neo4j:
    image: neo4j:5-community
    container_name: asagus-neo4j
    restart: unless-stopped
    environment:
      NEO4J_AUTH: neo4j/asagus-graph
      NEO4J_PLUGINS: '["apoc"]'
    ports:
      - "7474:7474"
      - "7687:7687"
    volumes:
      - asagus_neo4j_data:/data
    healthcheck:
      test: ["CMD-SHELL", "wget -qO- http://localhost:7474 || exit 1"]
      interval: 15s
      timeout: 10s
      retries: 5

  # ── MinIO (Object Storage for Raw HTML) ─────────────────────────
  minio:
    image: minio/minio:latest
    container_name: asagus-minio
    restart: unless-stopped
    environment:
      MINIO_ROOT_USER: asagus-access
      MINIO_ROOT_PASSWORD: asagus-secret
    command: server /data --console-address ":9001"
    ports:
      - "9000:9000"
      - "9001:9001"
    volumes:
      - asagus_minio_data:/data
    healthcheck:
      test: ["CMD", "mc", "ready", "local"]
      interval: 15s
      timeout: 10s
      retries: 3

volumes:
  asagus_postgres_data:
  asagus_redis_data:
  asagus_opensearch_data:
  asagus_qdrant_data:
  asagus_neo4j_data:
  asagus_minio_data:
COMPOSE_EOF

    log_info "Generated docker-compose.databases.yml"
}

# ── Generate PostgreSQL init script ────────────────────────────────
generate_init_sql() {
    cat > "$SCRIPT_DIR/init_postgres.sql" << 'SQL_EOF'
-- ============================================================
-- ASAGUS Scraper v3.0 — PostgreSQL Schema Initialization
-- Creates primary and secondary databases with required tables
-- ============================================================

-- Primary DB: Stores successful scraping results
CREATE TABLE IF NOT EXISTS records (
    id              SERIAL PRIMARY KEY,
    job_id          VARCHAR(128),
    source_url      TEXT NOT NULL,
    source          VARCHAR(64),
    name            TEXT DEFAULT '',
    phone           VARCHAR(64) DEFAULT '',
    email           VARCHAR(255) DEFAULT '',
    whatsapp        VARCHAR(64) DEFAULT '',
    address         TEXT DEFAULT '',
    city            VARCHAR(128) DEFAULT '',
    website_url     TEXT DEFAULT '',
    facebook_url    TEXT DEFAULT '',
    instagram_url   TEXT DEFAULT '',
    twitter_url     TEXT DEFAULT '',
    linkedin_url    TEXT DEFAULT '',
    rating          DECIMAL(3,2),
    review_count    INTEGER,
    category        VARCHAR(255) DEFAULT '',
    confidence      DECIMAL(4,3) DEFAULT 0.0,
    method          VARCHAR(64) DEFAULT '',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    raw_fields      JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_records_job_id ON records(job_id);
CREATE INDEX IF NOT EXISTS idx_records_email ON records(email) WHERE email != '';
CREATE INDEX IF NOT EXISTS idx_records_domain ON records(website_url);
CREATE INDEX IF NOT EXISTS idx_records_created ON records(created_at);

-- Secondary DB: Stores ALL processing events (including skips, failures)
CREATE TABLE IF NOT EXISTS secondary_records (
    id              SERIAL PRIMARY KEY,
    job_id          VARCHAR(128),
    url             TEXT NOT NULL,
    domain          VARCHAR(255) DEFAULT '',
    status          VARCHAR(32) NOT NULL,  -- stored, skipped, duplicate, failed, timeout, deferred
    method          VARCHAR(64) DEFAULT '',
    error_reason    TEXT DEFAULT '',
    query           TEXT DEFAULT '',
    location        TEXT DEFAULT '',
    mode            VARCHAR(32) DEFAULT '',
    processed_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_secondary_job_id ON secondary_records(job_id);
CREATE INDEX IF NOT EXISTS idx_secondary_status ON secondary_records(status);
CREATE INDEX IF NOT EXISTS idx_secondary_processed ON secondary_records(processed_at);

-- Jobs table: Track job metadata
CREATE TABLE IF NOT EXISTS jobs (
    id              VARCHAR(128) PRIMARY KEY,
    query           TEXT NOT NULL,
    location        TEXT DEFAULT '',
    mode            VARCHAR(32) DEFAULT 'balanced',
    status          VARCHAR(32) DEFAULT 'pending',
    max_results     INTEGER DEFAULT 100,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    completed_at    TIMESTAMPTZ,
    records_found   INTEGER DEFAULT 0,
    records_stored  INTEGER DEFAULT 0,
    config          JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_created ON jobs(created_at);

-- LLM settings persistence
CREATE TABLE IF NOT EXISTS settings (
    key             VARCHAR(128) PRIMARY KEY,
    value           TEXT NOT NULL,
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO asagus;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO asagus;
SQL_EOF

    log_info "Generated init_postgres.sql"
}

# ── Health check function ──────────────────────────────────────────
check_health() {
    log_step "Checking service health..."
    local services=("postgres:5432" "redis:6379" "opensearch:9200" "qdrant:6333" "neo4j:7687" "minio:9000")
    local all_healthy=true

    for service in "${services[@]}"; do
        local name="${service%%:*}"
        local port="${service##*:}"

        if docker ps --format '{{.Names}}' 2>/dev/null | grep -q "asagus-$name"; then
            log_info "  ✓ $name (port $port) — running"
        else
            log_warn "  ✗ $name (port $port) — not running"
            all_healthy=false
        fi
    done

    if $all_healthy; then
        log_info "All services are healthy!"
    else
        log_warn "Some services are not running. Try: ./setup_databases.sh --start"
    fi
}

# ── Main command handler ───────────────────────────────────────────
main() {
    local action="${1:---start}"

    # Check Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed. Please install Docker first."
        log_info "Visit: https://docs.docker.com/get-docker/"
        exit 1
    fi

    if ! docker compose version &> /dev/null 2>&1 && ! docker-compose version &> /dev/null 2>&1; then
        log_error "Docker Compose is not available."
        exit 1
    fi

    # Determine compose command
    local COMPOSE_CMD="docker compose"
    if ! docker compose version &> /dev/null 2>&1; then
        COMPOSE_CMD="docker-compose"
    fi

    case "$action" in
        --start|-s)
            echo ""
            echo "════════════════════════════════════════════════════════════"
            echo "  ASAGUS Scraper v3.0 — Database Infrastructure Setup"
            echo "════════════════════════════════════════════════════════════"
            echo ""
            generate_compose
            generate_init_sql
            log_step "Starting all database services..."
            $COMPOSE_CMD -f "$COMPOSE_FILE" up -d
            echo ""
            log_info "Waiting 15s for services to initialize..."
            sleep 15
            check_health
            echo ""
            log_info "Database URLs for .env:"
            echo "  POSTGRES_URL=postgresql://asagus:asagus@localhost:5432/asagus"
            echo "  REDIS_URL=redis://localhost:6379/0"
            echo "  OPENSEARCH_HOST=http://localhost:9200"
            echo "  QDRANT_HOST=http://localhost:6333"
            echo "  NEO4J_URI=bolt://localhost:7687"
            echo "  MINIO_ENDPOINT=localhost:9000"
            echo ""
            ;;
        --stop|-x)
            log_step "Stopping all database services..."
            $COMPOSE_CMD -f "$COMPOSE_FILE" down
            log_info "All services stopped."
            ;;
        --status)
            check_health
            ;;
        --reset)
            log_warn "This will DELETE all data. Are you sure? (y/N)"
            read -r confirm
            if [[ "$confirm" =~ ^[Yy]$ ]]; then
                log_step "Resetting all databases..."
                $COMPOSE_CMD -f "$COMPOSE_FILE" down -v
                log_info "All data has been reset."
            else
                log_info "Reset cancelled."
            fi
            ;;
        --help|-h)
            echo "ASAGUS Database Setup"
            echo "Usage: $0 [--start|--stop|--status|--reset|--help]"
            echo ""
            echo "Options:"
            echo "  --start, -s   Start all database services (default)"
            echo "  --stop, -x    Stop all database services"
            echo "  --status      Check service health"
            echo "  --reset       Stop and delete all data (destructive)"
            echo "  --help, -h    Show this help"
            ;;
        *)
            log_error "Unknown option: $action"
            echo "Use --help for usage information."
            exit 1
            ;;
    esac
}

main "$@"
