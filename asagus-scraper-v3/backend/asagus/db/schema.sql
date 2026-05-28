CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS scrape_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query TEXT NOT NULL,
    location TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    mode TEXT NOT NULL DEFAULT 'balanced',
    limit_requested INTEGER NOT NULL DEFAULT 100,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    skipped_targets INTEGER NOT NULL DEFAULT 0,
    duplicate_skips INTEGER NOT NULL DEFAULT 0,
    current_url TEXT NOT NULL DEFAULT '',
    progress_message TEXT NOT NULL DEFAULT '',
    error TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS businesses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    google_maps_id TEXT UNIQUE,
    name TEXT NOT NULL DEFAULT '',
    phone TEXT,
    whatsapp TEXT,
    email TEXT,
    email_verified BOOLEAN DEFAULT FALSE,
    address TEXT,
    city TEXT,
    country_code CHAR(2),
    lat NUMERIC(10,7),
    lng NUMERIC(10,7),
    website_url TEXT,
    has_website BOOLEAN GENERATED ALWAYS AS (website_url IS NOT NULL AND website_url <> '') STORED,
    facebook_url TEXT,
    instagram_url TEXT,
    twitter_url TEXT,
    linkedin_url TEXT,
    rating NUMERIC(2,1),
    review_count INTEGER,
    category TEXT,
    isic_code TEXT,
    record_completeness NUMERIC(3,2),
    source TEXT,
    gdpr_flag BOOLEAN DEFAULT FALSE,
    index_pending BOOLEAN DEFAULT TRUE,
    scraped_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_businesses_city ON businesses(city);
CREATE INDEX IF NOT EXISTS idx_businesses_has_website ON businesses(has_website);
CREATE INDEX IF NOT EXISTS idx_businesses_email ON businesses(email);
CREATE INDEX IF NOT EXISTS idx_businesses_phone ON businesses(phone);
CREATE INDEX IF NOT EXISTS idx_businesses_category ON businesses(category);

CREATE TABLE IF NOT EXISTS extraction_metadata (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID REFERENCES businesses(id) ON DELETE CASCADE,
    source_url TEXT NOT NULL,
    method TEXT NOT NULL,
    confidence NUMERIC(4,3) NOT NULL DEFAULT 0,
    selector_used TEXT,
    dom_fingerprint TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS policy_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    layer TEXT NOT NULL,
    domain TEXT NOT NULL DEFAULT '',
    event_type TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID,
    layer TEXT NOT NULL,
    event_type TEXT NOT NULL,
    message TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS relationship_candidates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_business_id UUID REFERENCES businesses(id) ON DELETE CASCADE,
    target_business_id UUID REFERENCES businesses(id) ON DELETE CASCADE,
    edge_type TEXT NOT NULL,
    confidence NUMERIC(4,3) NOT NULL,
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    status TEXT NOT NULL DEFAULT 'candidate',
    created_at TIMESTAMPTZ DEFAULT now()
);
