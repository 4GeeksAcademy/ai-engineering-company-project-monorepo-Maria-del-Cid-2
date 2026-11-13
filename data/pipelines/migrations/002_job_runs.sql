-- Scheduler-level execution history and idempotency, separate from
-- reporting.pipeline_runs (which records business-pipeline attempts).
CREATE SCHEMA IF NOT EXISTS reporting;

CREATE TABLE IF NOT EXISTS reporting.job_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_name TEXT NOT NULL,
    target_date DATE NOT NULL,
    attempt INTEGER NOT NULL CHECK (attempt > 0),
    status TEXT NOT NULL CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_job_runs_attempt UNIQUE (job_name, target_date, attempt),
    CONSTRAINT ck_job_runs_finish_state CHECK (
        (status IN ('pending', 'processing') AND finished_at IS NULL)
        OR (status IN ('completed', 'failed') AND finished_at IS NOT NULL)
    )
);

-- Only one completed record is needed to permanently satisfy idempotency;
-- failed/abandoned attempts remain available as history and can be retried.
CREATE UNIQUE INDEX IF NOT EXISTS uq_job_runs_completed_target
    ON reporting.job_runs (job_name, target_date)
    WHERE status = 'completed';

CREATE INDEX IF NOT EXISTS idx_job_runs_latest
    ON reporting.job_runs (job_name, target_date, attempt DESC);

CREATE INDEX IF NOT EXISTS idx_job_runs_processing
    ON reporting.job_runs (job_name, started_at)
    WHERE status = 'processing';
