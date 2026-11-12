# Nightly export scheduler (Phase 3)

The scheduler is a separate container, not part of FastAPI. It starts with the
Compose stack and launches `scripts/nightly_export.py` once daily at 02:00 UTC.
`NIGHTLY_EXPORT_AUDIT_DIR` defaults to `/var/lib/nightly-export/audit`, backed
by the persistent `nightly_export_audit` volume. Scheduler output is available
on stdout/stderr:

CSV publication and retention coordinate through OS-managed locks in the
volume's `.locks` directory. The exporter holds the per-file lock across the
temporary write and atomic replacement; a cleaner must acquire that same lock
before deletion. These locks are released by the OS when a process/container
exits. Lock files are stable and are intentionally not removed. The nightly
scheduler uses Docker's `json-file` log rotation, capped at ten 10 MiB files
(about 100 MiB); this is a size bound, not a fixed time-based retention period.
The independent `retention-scheduler` also uses stdout JSON logs and the same
rotation limit. Its UTC schedule defaults to 03:00 and can be changed with
`RETENTION_SCHEDULE_UTC=HH:MM`; it shares the `nightly_export_audit` volume and
artifact directory with the 02:00 export scheduler.

```powershell
docker compose up -d --build nightly-scheduler
docker compose up -d --build retention-scheduler
docker compose logs -f nightly-scheduler
docker compose logs -f retention-scheduler
docker compose stop nightly-scheduler
docker compose stop retention-scheduler
docker compose start nightly-scheduler
docker compose restart nightly-scheduler
docker compose down                 # leaves named CSV volume intact
docker volume ls                    # inspect named volume
```

For a one-off run, use `docker compose exec nightly-scheduler python
/app/scripts/nightly_export.py --target-date YYYY-MM-DD`.

## Isolated PostgreSQL integration tests

These tests need a disposable local PostgreSQL server and refuse known Supabase,
the persistent `reporting-db`, and databases not clearly named as tests. The
Compose profile uses PostgreSQL 16 on localhost:55432 with a **tmpfs database**;
the database disappears when stopped/removed and is separate from application
volumes. It is never configured with `.env` credentials.

```powershell
docker compose --profile integration up -d --wait postgres-integration
$env:JOB_RUNNER_TEST_DATABASE_URL = 'postgresql://phase3_test:phase3_test_only@127.0.0.1:55432/test_job_runner'
services/api/.venv/Scripts/python.exe -m pytest services/tests/test_postgres_job_runner_integration.py -q
docker compose --profile integration down
Remove-Item Env:JOB_RUNNER_TEST_DATABASE_URL
```

The suite exercises independent client processes and PostgreSQL sessions,
including hard-killing a client during a `processing` attempt and confirming
the next owner recovers it as failed before creating attempt 2. Do not change
the test URL to production, Supabase, or the normal `reporting-db`.

## Retention boundary

Daily CSV exports are temporary local audit artifacts. The independent
retention manager keeps exports dated today through 30 UTC calendar days ago
(inclusive) and removes matching exports older than 30 days. It excludes `.tmp`
and non-matching files and does not touch telemetry rows, weekly reports,
`reporting.pipeline_runs`, or `reporting.job_runs`. There is no external archive
or database audit table. Deletion outcomes are JSON logs emitted to stdout and
retained subject to the Docker log rotation limit above.