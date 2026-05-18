-- Enable extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;  -- for gen_random_uuid()

-- =========================================================
-- ACTIONS
-- =========================================================
CREATE TABLE actions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    site_id         INTEGER NOT NULL,
    wp_post_id      INTEGER NOT NULL,

    title           TEXT NOT NULL,
    description_html TEXT,
    description_text TEXT,
    steps_to_take_html TEXT,
    steps_to_take_text TEXT,
    deep_dive_html  TEXT,
    deep_dive_text  TEXT,

    is_featured     BOOLEAN DEFAULT FALSE,
    display_order   INTEGER,

    category        TEXT,
    sub_category    TEXT,

    url             TEXT,
    status          TEXT NOT NULL,
    modified_at     TIMESTAMPTZ,

    -- Tracking for incremental sync
    content_hash    TEXT,
    ingested_at     TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE (site_id, wp_post_id)
);

CREATE INDEX idx_actions_site ON actions(site_id);
CREATE INDEX idx_actions_category ON actions(site_id, category);
CREATE INDEX idx_actions_featured ON actions(site_id, is_featured) WHERE is_featured = TRUE;


-- =========================================================
-- TESTIMONIALS
-- =========================================================
CREATE TABLE testimonials (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    site_id         INTEGER NOT NULL,
    wp_post_id      INTEGER NOT NULL,

    title           TEXT,
    body_html       TEXT,
    body_text       TEXT,

    submitted_by    TEXT,
    display_name    TEXT,

    related_action_wp_post_id INTEGER,
    related_action_id UUID REFERENCES actions(id) ON DELETE SET NULL,

    display_order   INTEGER,
    status          TEXT NOT NULL,
    modified_at     TIMESTAMPTZ,

    content_hash    TEXT,
    ingested_at     TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE (site_id, wp_post_id)
);

CREATE INDEX idx_testimonials_site ON testimonials(site_id);
CREATE INDEX idx_testimonials_action ON testimonials(related_action_id);


-- =========================================================
-- EVENTS
-- =========================================================
CREATE TABLE events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    site_id         INTEGER NOT NULL,
    wp_post_id      INTEGER NOT NULL,

    title           TEXT NOT NULL,
    description_html TEXT,
    description_text TEXT,

    start_datetime_utc   TIMESTAMPTZ,
    end_datetime_utc     TIMESTAMPTZ,
    start_datetime_local TIMESTAMP,
    end_datetime_local   TIMESTAMP,
    timezone        TEXT,

    venue_name      TEXT,
    venue_address   TEXT,

    organizer_names  TEXT,    -- comma-separated
    organizer_emails TEXT,    -- comma-separated

    event_url       TEXT,
    cost            TEXT,     -- TEXT, not numeric: handles "Free", "$25", "Sliding scale"

    status          TEXT NOT NULL,
    modified_at     TIMESTAMPTZ,

    content_hash    TEXT,
    ingested_at     TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE (site_id, wp_post_id)
);

CREATE INDEX idx_events_site ON events(site_id);
CREATE INDEX idx_events_upcoming ON events(site_id, start_datetime_utc)
    WHERE status = 'publish';


-- =========================================================
-- EMBEDDINGS (one table, polymorphic)
-- =========================================================
CREATE TABLE embeddings (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    content_type    TEXT NOT NULL,    -- 'action' | 'testimonial' | 'event'
    content_id      UUID NOT NULL,    -- fk to one of the three tables above
    site_id         INTEGER NOT NULL, -- denormalized for fast filtering

    chunk_index     INTEGER NOT NULL DEFAULT 0,
    chunk_text      TEXT NOT NULL,    -- the actual text that was embedded
    embedding       vector(1024),     -- dimension TBD, see notes below

    embedding_model TEXT NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE (content_type, content_id, chunk_index)
);

CREATE INDEX idx_embeddings_site ON embeddings(site_id);
CREATE INDEX idx_embeddings_type ON embeddings(content_type);

-- Vector similarity index (HNSW is the modern default for pgvector)
CREATE INDEX idx_embeddings_vector ON embeddings
    USING hnsw (embedding vector_cosine_ops);