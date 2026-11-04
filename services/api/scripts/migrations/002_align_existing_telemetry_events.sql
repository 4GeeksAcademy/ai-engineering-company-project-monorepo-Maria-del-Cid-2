-- Align the manually created Supabase table with Nexova's approved telemetry
-- contract. This migration never drops or recreates telemetry_events.
--
-- Run only after confirming existing rows fit the new constraints.

ALTER TABLE public.telemetry_events
    ALTER COLUMN id SET GENERATED ALWAYS,
    ALTER COLUMN event_id DROP DEFAULT,
    ALTER COLUMN event_type TYPE VARCHAR(100) USING event_type::VARCHAR(100),
    ALTER COLUMN source TYPE VARCHAR(255) USING source::VARCHAR(255),
    ALTER COLUMN session_id TYPE VARCHAR(100) USING session_id::VARCHAR(100),
    ALTER COLUMN schema_version TYPE VARCHAR(20) USING schema_version::VARCHAR(20),
    ALTER COLUMN event_id SET NOT NULL,
    ALTER COLUMN event_type SET NOT NULL,
    ALTER COLUMN timestamp SET NOT NULL,
    ALTER COLUMN source SET NOT NULL,
    ALTER COLUMN tags SET NOT NULL,
    ADD CONSTRAINT telemetry_events_event_id_key UNIQUE (event_id);

ALTER INDEX public.idx_telemetry_events_tags
    RENAME TO idx_telemetry_events_tags_gin;
