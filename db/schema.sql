-- Database Schema for Real-Time Job Posting Tracker

-- 1. Postings table: stores raw and normalized job/internship listings
CREATE TABLE IF NOT EXISTS postings (
    id SERIAL PRIMARY KEY,
    source VARCHAR(100) NOT NULL,          -- e.g. 'simplify_github', 'greenhouse_cloudflare'
    external_id TEXT NOT NULL,             -- unique id from the source
    company TEXT NOT NULL,
    title TEXT NOT NULL,
    location TEXT,                         -- handles multi-location lists
    terms TEXT,                            -- e.g. 'Summer 2027', 'Fall 2026'
    is_remote BOOLEAN DEFAULT FALSE,
    url TEXT,
    posted_at TIMESTAMP WITH TIME ZONE,
    first_seen_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_seen_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE,
    raw_json JSONB,
    search_vector tsvector GENERATED ALWAYS AS (
        to_tsvector('english', coalesce(company, '') || ' ' || coalesce(title, '') || ' ' || coalesce(location, '') || ' ' || coalesce(terms, ''))
    ) STORED,
    UNIQUE(source, external_id)
);

CREATE INDEX IF NOT EXISTS idx_postings_search ON postings USING GIN(search_vector);
CREATE INDEX IF NOT EXISTS idx_postings_active ON postings(is_active);
CREATE INDEX IF NOT EXISTS idx_postings_company ON postings(company);
CREATE INDEX IF NOT EXISTS idx_postings_terms ON postings(terms);
CREATE INDEX IF NOT EXISTS idx_postings_first_seen ON postings(first_seen_at DESC);

-- 2. Users table: Telegram subscribers and preferences
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    telegram_chat_id BIGINT UNIQUE NOT NULL,
    username VARCHAR(255),
    notification_mode VARCHAR(50) DEFAULT 'instant', -- 'instant' | 'daily_digest' | 'paused'
    digest_hour INT DEFAULT 18,                      -- 18:00 (6 PM) default
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 3. Subscriptions table: user watchlists/filters
CREATE TABLE IF NOT EXISTS subscriptions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    company_filter TEXT,                             -- NULL = any company
    keyword_filter TEXT,                             -- NULL = any keyword, matches title
    location_filter TEXT,                            -- NULL = any location
    term_filter TEXT,                                -- e.g. 'Summer 2027', 'Fall 2026'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_subscriptions_user_id ON subscriptions(user_id);

-- 4. Notifications sent: deduplication log
CREATE TABLE IF NOT EXISTS notifications_sent (
    id SERIAL PRIMARY KEY,
    posting_id INTEGER NOT NULL REFERENCES postings(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    sent_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(posting_id, user_id)
);

-- 5. Skill mentions (for Phase 4 trend tracking)
CREATE TABLE IF NOT EXISTS skill_mentions (
    id SERIAL PRIMARY KEY,
    posting_id INTEGER NOT NULL REFERENCES postings(id) ON DELETE CASCADE,
    skill VARCHAR(100) NOT NULL,
    category VARCHAR(50),
    extracted_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(posting_id, skill)
);

CREATE INDEX IF NOT EXISTS idx_skill_mentions_skill ON skill_mentions(skill);
CREATE INDEX IF NOT EXISTS idx_skill_mentions_category ON skill_mentions(category);
