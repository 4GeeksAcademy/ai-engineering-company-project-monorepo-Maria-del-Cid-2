"""Real PostgreSQL integration tests; only run against an explicit test URL.

Set JOB_RUNNER_TEST_DATABASE_URL to a disposable, isolated PostgreSQL database.
Never point this suite at Supabase or the persistent Compose reporting-db.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from datetime import date
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest

SERVICES = Path(__file__).resolve().parents[1]
REPO = SERVICES.parent
sys.path.insert(0, str(SERVICES))
sys.path.insert(0, str(REPO / "scripts"))

import job_runner  # noqa: E402
import nightly_export  # noqa: E402

TEST_DATABASE_URL = os.environ.get("JOB_RUNNER_TEST_DATABASE_URL", "").strip()
MIGRATION = REPO / "data" / "pipelines" / "migrations" / "002_job_runs.sql"
PIPELINE_MIGRATION = REPO / "data" / "pipelines" / "migrations" / "001_reporting.sql"

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="Set JOB_RUNNER_TEST_DATABASE_URL to an isolated disposable PostgreSQL database",
)


@pytest.fixture(scope="session", autouse=True)
def isolated_database_guard():
    """Apply the scheduler schema only after rejecting known unsafe endpoints."""
    parsed = psycopg.conninfo.conninfo_to_dict(TEST_DATABASE_URL)
    host = (parsed.get("host") or "").lower()
    database = (parsed.get("dbname") or "").lower()
    assert host not in {"reporting-db", "db.yamhkvudzwcqsbqvfmox.supabase.co"}, (
        "integration tests cannot use the persistent Compose DB or Supabase"
    )
    assert "supabase" not in host and database != "postgres", "unsafe integration target"
    assert database.startswith("test_") or "test" in database, (
        "integration target database name must explicitly contain test"
    )
    with psycopg.connect(TEST_DATABASE_URL, autocommit=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute(PIPELINE_MIGRATION.read_text(encoding="utf-8"))
            cursor.execute(MIGRATION.read_text(encoding="utf-8"))
    yield


def _url_for_runner(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REPORTING_DATABASE_URL", TEST_DATABASE_URL)


def _query(sql: str, params: tuple[object, ...] = ()) -> list[tuple[object, ...]]:
    with psycopg.connect(TEST_DATABASE_URL) as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql, params)
            return cursor.fetchall()


def _worker_source() -> str:
    return r'''
import os, sys, time
from datetime import date
sys.path.insert(0, os.environ["JOB_RUNNER_SERVICES"])
from job_runner import JobRunner
name = os.environ["JOB_RUNNER_NAME"]
mode = os.environ.get("JOB_RUNNER_MODE", "hold")
lease = JobRunner().acquire(name, date.fromisoformat(os.environ["JOB_RUNNER_DATE"]))
if lease is None:
    print("BUSY", flush=True)
    raise SystemExit(3)
print(f"ACQUIRED {lease.run_id} {lease.attempt}", flush=True)
if mode == "hold":
    while True:
        time.sleep(0.1)
lease.complete()
print("COMPLETED", flush=True)
'''


def _process_env(monkeypatch: pytest.MonkeyPatch, name: str, target: date, mode: str = "hold") -> dict[str, str]:
    return {
        **os.environ,
        "REPORTING_DATABASE_URL": TEST_DATABASE_URL,
        "JOB_RUNNER_SERVICES": str(SERVICES),
        "JOB_RUNNER_NAME": name,
        "JOB_RUNNER_DATE": target.isoformat(),
        "JOB_RUNNER_MODE": mode,
    }


def test_real_sessions_exclude_concurrent_process_and_allow_release(monkeypatch: pytest.MonkeyPatch) -> None:
    _url_for_runner(monkeypatch)
    name = f"integration-concurrency-{uuid4()}"
    target = date(2026, 10, 1)
    process = subprocess.Popen(
        [sys.executable, "-u", "-c", _worker_source()],
        env=_process_env(monkeypatch, name, target),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert process.stdout is not None
        assert process.stdout.readline().startswith("ACQUIRED ")
        assert job_runner.JobRunner().acquire(name, target) is None
    finally:
        process.terminate()
        process.wait(timeout=15)
    # Closing the killed process's PostgreSQL session released the real session lock.
    lease = job_runner.JobRunner().acquire(name, target)
    assert lease is not None
    lease.complete()


def test_killed_process_lock_is_released_and_abandoned_attempt_recovered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _url_for_runner(monkeypatch)
    name = f"integration-recovery-{uuid4()}"
    target = date(2026, 10, 2)
    process = subprocess.Popen(
        [sys.executable, "-u", "-c", _worker_source()],
        env=_process_env(monkeypatch, name, target),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert process.stdout is not None
    first_line = process.stdout.readline()
    assert first_line.startswith("ACQUIRED "), process.stderr.read() if process.stderr else ""
    first_id = first_line.split()[1]
    # Abrupt termination deliberately bypasses JobRunLease.__exit__/fail().
    process.kill()
    process.wait(timeout=15)

    second = job_runner.JobRunner().acquire(name, target)
    assert second is not None, "second independent process/session must take the released advisory lock"
    assert second.attempt == 2
    rows = _query(
        "SELECT id::text, attempt, status, error_message FROM reporting.job_runs "
        "WHERE job_name = %s AND target_date = %s ORDER BY attempt",
        (name, target),
    )
    assert rows[0][0] == first_id
    assert rows[0][1:3] == (1, "failed")
    assert "Recovered abandoned attempt" in rows[0][3]
    assert rows[1][1:3] == (2, "processing")
    second.complete()
    final_rows = _query(
        "SELECT attempt, status FROM reporting.job_runs WHERE job_name = %s AND target_date = %s ORDER BY attempt",
        (name, target),
    )
    assert final_rows == [(1, "failed"), (2, "completed")]


def test_completed_target_is_idempotent_and_failed_attempt_is_retained(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _url_for_runner(monkeypatch)
    name = f"integration-idempotency-{uuid4()}"
    target = date(2026, 10, 3)
    first = job_runner.JobRunner().acquire(name, target)
    assert first is not None
    first.complete()
    assert job_runner.JobRunner().acquire(name, target) is None
    retry_target = date(2026, 10, 4)
    failed = job_runner.JobRunner().acquire(name, retry_target)
    assert failed is not None
    failed.fail("intentional integration failure")
    retry = job_runner.JobRunner().acquire(name, retry_target)
    assert retry is not None and retry.attempt == 2
    retry.complete()
    rows = _query(
        "SELECT attempt, status FROM reporting.job_runs WHERE job_name = %s AND target_date = %s ORDER BY attempt",
        (name, retry_target),
    )
    assert rows == [(1, "failed"), (2, "completed")]


def test_advisory_locks_are_session_scoped_on_configured_test_endpoint() -> None:
    key = f"phase3-probe-{uuid4()}"
    owner = psycopg.connect(TEST_DATABASE_URL, autocommit=True)
    try:
        with owner.cursor() as cursor:
            cursor.execute("SELECT pg_try_advisory_lock(hashtextextended(%s, 0))", (key,))
            assert cursor.fetchone()[0] is True
            with psycopg.connect(TEST_DATABASE_URL, autocommit=True) as contender:
                with contender.cursor() as second_cursor:
                    second_cursor.execute("SELECT pg_try_advisory_lock(hashtextextended(%s, 0))", (key,))
                    assert second_cursor.fetchone()[0] is False
    finally:
        owner.close()
    with psycopg.connect(TEST_DATABASE_URL, autocommit=True) as successor:
        with successor.cursor() as cursor:
            cursor.execute("SELECT pg_try_advisory_lock(hashtextextended(%s, 0))", (key,))
            assert cursor.fetchone()[0] is True
            cursor.execute("SELECT pg_advisory_unlock(hashtextextended(%s, 0))", (key,))
            assert cursor.fetchone()[0] is True


def test_nightly_success_duplicate_and_job_history_separation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    _url_for_runner(monkeypatch)
    name = f"integration-e2e-success-{uuid4()}"
    monkeypatch.setattr(job_runner, "DEFAULT_JOB_NAME", name)
    monkeypatch.setattr(nightly_export, "DEFAULT_JOB_NAME", name)
    target = date(2026, 10, 5)
    output = tmp_path / "audit.csv"
    pipeline_runs_before = _query("SELECT count(*) FROM reporting.pipeline_runs")[0][0]

    def exporter(_target: date) -> Path:
        output.write_text("event_id,event_type,timestamp,tags\n", encoding="utf-8")
        return output

    class PipelineResult:
        returncode = 0
        stdout = ""
        stderr = ""

    result = nightly_export.run_nightly_export(
        target,
        process_runner=lambda *_args, **_kwargs: PipelineResult(),
        audit_exporter=exporter,
    )
    assert result == 0 and output.exists()
    # Re-running a completed date is idempotently skipped before exporter or pipeline.
    assert nightly_export.run_nightly_export(
        target,
        process_runner=lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("pipeline reran")),
        audit_exporter=lambda *_args: (_ for _ in ()).throw(AssertionError("export reran")),
    ) == 0
    rows = _query(
        "SELECT attempt, status FROM reporting.job_runs WHERE job_name = %s AND target_date = %s",
        (name, target),
    )
    assert rows == [(1, "completed")]
    pipeline_runs_after = _query("SELECT count(*) FROM reporting.pipeline_runs")[0][0]
    assert pipeline_runs_after == pipeline_runs_before, (
        "the fake business runner must not create business pipeline history"
    )


def test_real_business_pipeline_subprocess_records_separate_pipeline_history(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    _url_for_runner(monkeypatch)
    name = f"integration-e2e-real-pipeline-{uuid4()}"
    monkeypatch.setattr(job_runner, "DEFAULT_JOB_NAME", name)
    monkeypatch.setattr(nightly_export, "DEFAULT_JOB_NAME", name)
    target = date(2026, 10, 12)
    week_start = nightly_export.iso_week_start(target)
    monkeypatch.setenv("TELEMETRY_DATABASE_URL", TEST_DATABASE_URL)
    with psycopg.connect(TEST_DATABASE_URL, autocommit=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "CREATE TABLE IF NOT EXISTS public.telemetry_events ("
                "event_id TEXT PRIMARY KEY, event_type TEXT NOT NULL, "
                "timestamp TIMESTAMPTZ NOT NULL, tags JSONB NOT NULL DEFAULT '{}'::jsonb)"
            )
            cursor.execute("TRUNCATE public.telemetry_events")

    def run_pipeline(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        child_env = {
            **os.environ,
            "REPORTING_DATABASE_URL": TEST_DATABASE_URL,
            "TELEMETRY_DATABASE_URL": TEST_DATABASE_URL,
            "PREFECT_HOME": str(tmp_path / "prefect-home"),
            "REPORTING_SNAPSHOT_DIR": str(tmp_path / "snapshots"),
        }
        subprocess_kwargs = dict(kwargs)
        subprocess_kwargs["env"] = child_env
        return subprocess.run(
            command,
            **subprocess_kwargs,  # type: ignore[arg-type]
        )

    def exporter(_target: date) -> Path:
        output = tmp_path / "real-e2e-audit.csv"
        output.write_text("event_id,event_type,timestamp,tags\n", encoding="utf-8")
        return output

    assert nightly_export.run_nightly_export(
        target,
        process_runner=run_pipeline,
        audit_exporter=exporter,
    ) == 0
    business_rows = _query(
        "SELECT status, trigger_type FROM reporting.pipeline_runs "
        "WHERE pipeline_name = 'weekly_office_program_performance' AND week_start = %s",
        (week_start,),
    )
    assert business_rows and business_rows[-1] == ("completed", "scheduled")
    scheduler_rows = _query(
        "SELECT status FROM reporting.job_runs WHERE job_name = %s AND target_date = %s",
        (name, target),
    )
    assert scheduler_rows == [("completed",)]


@pytest.mark.parametrize("failure", ["export", "pipeline"])
def test_nightly_failures_are_retained_as_failed_attempts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, failure: str,
) -> None:
    _url_for_runner(monkeypatch)
    name = f"integration-e2e-{failure}-{uuid4()}"
    monkeypatch.setattr(job_runner, "DEFAULT_JOB_NAME", name)
    monkeypatch.setattr(nightly_export, "DEFAULT_JOB_NAME", name)
    target = date(2026, 10, 6 if failure == "export" else 7)

    class PipelineResult:
        returncode = 17
        stdout = ""
        stderr = "intentional pipeline integration failure"

    def exporter(_target: date) -> Path:
        if failure == "export":
            raise OSError("intentional export integration failure")
        path = tmp_path / f"{name}.csv"
        path.write_text("event_id,event_type,timestamp,tags\n", encoding="utf-8")
        return path

    with pytest.raises((OSError, RuntimeError)):
        nightly_export.run_nightly_export(
            target,
            process_runner=lambda *_args, **_kwargs: PipelineResult(),
            audit_exporter=exporter,
        )
    rows = _query(
        "SELECT attempt, status, error_message FROM reporting.job_runs "
        "WHERE job_name = %s AND target_date = %s",
        (name, target),
    )
    assert len(rows) == 1
    assert rows[0][0:2] == (1, "failed")
    assert "intentional" in rows[0][2]
