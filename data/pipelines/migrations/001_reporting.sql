-- Reporting history is committed independently from weekly KPI results.
CREATE SCHEMA IF NOT EXISTS reporting;

CREATE TABLE IF NOT EXISTS reporting.pipeline_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pipeline_name TEXT NOT NULL,
    week_start DATE NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    status TEXT NOT NULL CHECK (status IN ('running', 'completed', 'failed')),
    records_processed INTEGER NOT NULL DEFAULT 0,
    records_inserted INTEGER NOT NULL DEFAULT 0,
    records_updated INTEGER NOT NULL DEFAULT 0,
    records_rejected INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    trigger_type TEXT NOT NULL CHECK (trigger_type IN ('scheduled', 'manual')),
    requested_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_reporting_pipeline_runs_latest
    ON reporting.pipeline_runs (pipeline_name, started_at DESC);

CREATE TABLE IF NOT EXISTS reporting.weekly_office_program_performance (
    office TEXT NOT NULL CHECK (office IN ('Valencia', 'Miami')),
    programme_id TEXT NOT NULL,
    week_start DATE NOT NULL,
    total_material_cost NUMERIC(14, 2) NOT NULL DEFAULT 0,
    kits_delivered_count INTEGER NOT NULL DEFAULT 0,
    shortage_events_count INTEGER NOT NULL DEFAULT 0,
    cost_variance_events_count INTEGER NOT NULL DEFAULT 0,
    currency TEXT NOT NULL CHECK (currency IN ('EUR', 'USD')),
    computed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_weekly_office_program_performance
        UNIQUE (office, programme_id, week_start)
);
