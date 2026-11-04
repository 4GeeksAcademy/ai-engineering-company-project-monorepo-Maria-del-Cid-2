-- Telemetry storage schema for Nexova.
--
-- Apply explicitly against the intended Supabase PostgreSQL database. This
-- migration does not grant privileges or execute UPDATE/DELETE operations.

CREATE TABLE IF NOT EXISTS telemetry_events (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    event_id UUID NOT NULL UNIQUE,
    event_type VARCHAR(100) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    source VARCHAR(255) NOT NULL,
    session_id VARCHAR(100),
    schema_version VARCHAR(20),
    tags JSONB NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_telemetry_events_timestamp
    ON telemetry_events (timestamp);

CREATE INDEX IF NOT EXISTS idx_telemetry_events_event_type
    ON telemetry_events (event_type);

CREATE INDEX IF NOT EXISTS idx_telemetry_events_tags_gin
    ON telemetry_events USING GIN (tags);
