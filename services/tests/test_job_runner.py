"""Unit tests for scheduler run tracking and global lock behavior."""

from __future__ import annotations

import sys
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from uuid import uuid4

import pytest

SERVICES_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICES_DIR))

import job_runner  # noqa: E402

TARGET = date(2026, 11, 11)


class FakeCursor:
    def __init__(self, connection: "FakeConnection") -> None:
        self.connection = connection
        self.rowcount = -1
        self.result: tuple[object, ...] | None = None

    def __enter__(self) -> "FakeCursor":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def execute(self, query: str, params: tuple[object, ...] = ()) -> None:
        normalized = " ".join(query.split())
        self.connection.statements.append((normalized, params))
        if "pg_try_advisory_lock" in normalized:
            self.result = (self.connection.lock_available,)
        elif "SELECT 1 FROM reporting.job_runs" in normalized:
            self.result = (1,) if self.connection.completed else None
        elif "COALESCE(MAX(attempt)" in normalized:
            self.result = (self.connection.attempt,)
        elif "RETURNING id" in normalized:
            self.result = (self.connection.run_id,)
        elif "pg_advisory_unlock" in normalized:
            self.result = (True,)
        elif "WHERE status IN ('pending', 'processing')" in normalized:
            self.rowcount = self.connection.abandoned_rows
            self.result = None
        elif "SET status = 'failed'" in normalized and "WHERE id = %s" in normalized:
            if self.connection.fallback_failures:
                self.connection.fallback_failures -= 1
                raise OSError("database unavailable for fallback")
            self.rowcount = 1
            self.result = None
        elif "SET status = %s" in normalized:
            if self.connection.terminal_failures:
                self.connection.terminal_failures -= 1
                raise OSError("database unavailable for terminal update")
            self.rowcount = 1
            self.result = None
        else:
            self.rowcount = 1
            self.result = None

    def fetchone(self) -> tuple[object, ...] | None:
        return self.result


class FakeConnection:
    def __init__(
        self,
        *,
        lock_available: bool = True,
        completed: bool = False,
        attempt: int = 2,
        terminal_failures: int = 0,
        fallback_failures: int = 0,
        abandoned_rows: int = 0,
    ) -> None:
        self.lock_available = lock_available
        self.completed = completed
        self.attempt = attempt
        self.terminal_failures = terminal_failures
        self.fallback_failures = fallback_failures
        self.abandoned_rows = abandoned_rows
        self.run_id = uuid4()
        self.statements: list[tuple[str, tuple[object, ...]]] = []
        self.closed = False
        self.transaction_count = 0

    def cursor(self) -> FakeCursor:
        return FakeCursor(self)

    @contextmanager
    def transaction(self):
        self.transaction_count += 1
        yield

    def close(self) -> None:
        self.closed = True


def make_runner(monkeypatch: pytest.MonkeyPatch, connection: FakeConnection) -> job_runner.JobRunner:
    monkeypatch.setattr(job_runner, "get_reporting_database_url", lambda: "postgresql://test")
    return job_runner.JobRunner(connect=lambda *_args, **_kwargs: connection)


def test_acquire_uses_global_lock_and_creates_next_attempt(monkeypatch: pytest.MonkeyPatch) -> None:
    connection = FakeConnection(attempt=3)
    runner = make_runner(monkeypatch, connection)

    lease = runner.acquire("nightly_export", TARGET)

    assert lease is not None
    assert lease.run_id == connection.run_id
    assert lease.attempt == 3
    assert lease.target_date == TARGET
    lock_sql, lock_params = connection.statements[0]
    assert "pg_try_advisory_lock" in lock_sql
    assert lock_params == ("nightly-job:nightly_export",)
    recovery = next(sql for sql, _ in connection.statements if "Recovered abandoned attempt" in sql)
    assert "status IN ('pending', 'processing')" in recovery
    assert not connection.closed


def test_active_global_lock_skips_without_mutating_attempts(monkeypatch: pytest.MonkeyPatch) -> None:
    connection = FakeConnection(lock_available=False)
    runner = make_runner(monkeypatch, connection)

    assert runner.acquire("nightly_export", TARGET) is None
    assert connection.closed
    assert len(connection.statements) == 1


def test_completed_target_is_idempotently_skipped_and_unlocks(monkeypatch: pytest.MonkeyPatch) -> None:
    connection = FakeConnection(completed=True)
    runner = make_runner(monkeypatch, connection)

    assert runner.acquire("nightly_export", TARGET) is None
    assert any("pg_advisory_unlock" in sql for sql, _ in connection.statements)
    assert connection.closed
    assert not any("INSERT INTO reporting.job_runs" in sql for sql, _ in connection.statements)


def test_failed_attempt_is_preserved_and_lock_releases_on_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    connection = FakeConnection()
    lease = make_runner(monkeypatch, connection).acquire("nightly_export", TARGET)
    assert lease is not None

    lease.fail("temporary downstream failure")

    final_sql, params = next(
        (sql, params)
        for sql, params in connection.statements
        if "SET status = %s" in sql
    )
    assert "status = 'processing'" in final_sql
    assert params == ("failed", "temporary downstream failure", connection.run_id)
    assert connection.closed
    with pytest.raises(job_runner.JobRunnerError, match="already been released"):
        lease.complete()


def test_context_manager_records_exception_and_does_not_swallow_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = FakeConnection()
    lease = make_runner(monkeypatch, connection).acquire("nightly_export", TARGET)
    assert lease is not None

    with pytest.raises(RuntimeError, match="boom"):
        with lease:
            raise RuntimeError("boom")

    assert any(
        params[0] == "failed" and "RuntimeError: boom" in str(params[1])
        for sql, params in connection.statements
        if "SET status = %s" in sql
    )
    assert connection.closed


def test_completed_run_marks_terminal_state_before_releasing(monkeypatch: pytest.MonkeyPatch) -> None:
    connection = FakeConnection()
    lease = make_runner(monkeypatch, connection).acquire("nightly_export", TARGET)
    assert lease is not None

    lease.complete()

    finish_index = next(i for i, (sql, _) in enumerate(connection.statements) if "SET status = %s" in sql)
    assert connection.statements[finish_index][1][0] == "completed"
    assert connection.closed


def test_complete_failure_attempts_failed_fallback_and_closes_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = FakeConnection(terminal_failures=1)
    lease = make_runner(monkeypatch, connection).acquire("nightly_export", TARGET)
    assert lease is not None

    with pytest.raises(OSError, match="database unavailable for terminal update"):
        lease.complete()

    terminal_sql = [sql for sql, _ in connection.statements]
    assert any("SET status = %s" in sql for sql in terminal_sql)
    assert any("SET status = 'failed'" in sql for sql in terminal_sql)
    assert connection.closed
    assert lease._closed


def test_failed_state_write_preserves_original_error_and_adds_fallback_issue(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = FakeConnection(terminal_failures=1, fallback_failures=1)
    lease = make_runner(monkeypatch, connection).acquire("nightly_export", TARGET)
    assert lease is not None

    with pytest.raises(OSError, match="database unavailable for terminal update") as exc_info:
        lease.fail("pipeline failed")

    assert any(
        "Fallback update to failed also did not persist" in note
        for note in exc_info.value.__notes__
    )
    assert connection.closed


def test_next_acquire_recovers_abandoned_processing_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = FakeConnection(abandoned_rows=2)
    runner = make_runner(monkeypatch, connection)

    lease = runner.acquire("nightly_export", TARGET)

    assert lease is not None
    recovery_statement = next(
        (sql, params)
        for sql, params in connection.statements
        if "Recovered abandoned attempt" in sql
    )
    assert "status IN ('pending', 'processing')" in recovery_statement[0]
    assert recovery_statement[1] == ("nightly_export",)
    assert not connection.closed


def test_lock_not_acquired_does_not_attempt_recovery_or_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = FakeConnection(lock_available=False, abandoned_rows=3)
    runner = make_runner(monkeypatch, connection)

    assert runner.acquire("nightly_export", TARGET) is None

    assert len(connection.statements) == 1
    assert "pg_try_advisory_lock" in connection.statements[0][0]
    assert not any("UPDATE reporting.job_runs" in sql for sql, _ in connection.statements)
    assert connection.closed


def test_failed_terminal_update_logs_structured_context(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    connection = FakeConnection(terminal_failures=2)
    lease = make_runner(monkeypatch, connection).acquire("nightly_export", TARGET)
    assert lease is not None

    with caplog.at_level("ERROR", logger="job_runner"):
        with pytest.raises(OSError):
            lease.complete()

    record = next(record for record in caplog.records if record.status == "terminal_state_error")
    assert record.job_name == "nightly_export"
    assert record.target_date == TARGET.isoformat()
    assert connection.closed


def test_validation_rejects_datetime_as_target_date(monkeypatch: pytest.MonkeyPatch) -> None:
    connection = FakeConnection()
    runner = make_runner(monkeypatch, connection)

    with pytest.raises(TypeError, match="datetime.date"):
        runner.acquire("nightly_export", datetime.now())
    assert not connection.statements


def test_migration_defines_attempt_history_and_completed_idempotency_index() -> None:
    migration = SERVICES_DIR.parent / "data" / "pipelines" / "migrations" / "002_job_runs.sql"
    sql = migration.read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS reporting.job_runs" in sql
    assert "UNIQUE (job_name, target_date, attempt)" in sql
    assert "WHERE status = 'completed'" in sql
    assert "status IN ('pending', 'processing', 'completed', 'failed')" in sql
