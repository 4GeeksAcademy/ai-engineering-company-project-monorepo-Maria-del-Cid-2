-- Dedicated dead-letter storage for terminal Incident Analysis failures.
-- Apply only to the approved CELERY_DATABASE_URL target with SSL required.
-- Stores task metadata only; never CSV, task payload, row data, or raw exceptions.

CREATE TABLE IF NOT EXISTS public.celery_incident_analysis_dlq (
    task_id VARCHAR(128) PRIMARY KEY,
    task_name VARCHAR(100) NOT NULL,
    failed_at TIMESTAMPTZ NOT NULL,
    attempt_count SMALLINT NOT NULL CHECK (attempt_count BETWEEN 1 AND 3),
    error_type VARCHAR(100) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_celery_incident_analysis_dlq_failed_at
    ON public.celery_incident_analysis_dlq (failed_at);
