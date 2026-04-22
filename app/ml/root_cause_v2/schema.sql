-- Schema for the incident vector store backing root_cause_v2.
-- Requires PostgreSQL 14+ with the pgvector extension.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS incidents (
    incident_id         TEXT        PRIMARY KEY,
    ts                  TIMESTAMPTZ NOT NULL,
    device_class        TEXT        NOT NULL,
    text                TEXT        NOT NULL,
    root_cause          TEXT        NOT NULL,
    root_cause_detail   TEXT        NOT NULL,
    actions_taken       JSONB       NOT NULL DEFAULT '[]'::jsonb,
    resolution_minutes  INTEGER,
    confidence_label    REAL        NOT NULL DEFAULT 1.0,
    metadata            JSONB       NOT NULL DEFAULT '{}'::jsonb,
    embedding           vector(384) NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Approximate-nearest-neighbor index for fast cosine search.
-- IVFFlat is recommended once the table has > 1000 rows.
-- Tune `lists` as roughly sqrt(N).
CREATE INDEX IF NOT EXISTS incidents_embedding_idx
  ON incidents
  USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 100);

-- Filter helper for device-class-scoped queries.
CREATE INDEX IF NOT EXISTS incidents_device_class_idx
  ON incidents (device_class);

-- For audit / labeling workflows.
CREATE INDEX IF NOT EXISTS incidents_ts_idx
  ON incidents (ts DESC);
