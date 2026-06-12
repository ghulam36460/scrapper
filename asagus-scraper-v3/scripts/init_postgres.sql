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
