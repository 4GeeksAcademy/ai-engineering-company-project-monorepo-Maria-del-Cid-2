"""PostgreSQL-backed execution history and global job locking.

This scheduler-level state is intentionally separate from
``reporting.pipeline_runs``, which records individual business-pipeline runs.
"""

from __future__ import annotations

import os
import logging
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Callable, Self
from uuid import UUID

import psycopg

REPORTING_DATABASE_URL_ENV = "REPORTING_DATABASE_URL"
DEFAULT_JOB_NAME = "nightly_export"
logger = logging.getLogger("nightly_export")


class JobRunnerError(RuntimeError):
    """Raised when scheduler run state cannot be safely managed."""


class JobRunnerConfigurationError(JobRunnerError):
    """Raised when the reporting database configuration is invalid."""


def get_reporting_database_url() -> str:
    """Return and validate the PostgreSQL URL used by reporting storage."""
    value = os.environ.get(REPORTING_DATABASE_URL_ENV, "").strip()
    if not value:
        raise JobRunnerConfigurationError(f"{REPORTING_DATABASE_URL_ENV} is not configured")
    if not value.startswith(("postgresql://", "postgres://")):
        raise JobRunnerConfigurationError(f"{REPORTING_DATABASE_URL_ENV} must use a PostgreSQL URL")
    return value


def _validate_identity(job_name: str, target_date: date) -> None:
    if not job_name or not job_name.strip():
        raise ValueError("job_name must not be empty")
    if isinstance(target_date, datetime) or not isinstance(target_date, date):
        raise TypeError("target_date must be a datetime.date")


@dataclass
class JobRunLease:
    """An active run holding a session-level advisory lock for its job name."""

    run_id: UUID
    job_name: str
    target_date: date
    attempt: int
    _connection: Any
    _closed: bool = False

    def complete(self) -> None:
        """Mark this attempt completed, then release the global lock."""
        self._finish("completed", None)

    def fail(self, error_message: str) -> None:
        """Mark this attempt failed while preserving its history."""
        message = error_message.strip() or "Job failed without an error message"
        self._finish("failed", message[:4000])

    def _finish(self, status: str, error_message: str | None) -> None:
        if self._closed:
            raise JobRunnerError("this job run lease has already been released")
        finish_error: BaseException | None = None
        finish_traceback = None
        try:
            with self._connection.transaction():
                with self._connection.cursor() as cursor:
                    cursor.execute(
                        "UPDATE reporting.job_runs "
                        "SET status = %s, finished_at = now(), error_message = %s "
                        "WHERE id = %s AND status = 'processing'",
                        (status, error_message, self.run_id),
                    )
                    if cursor.rowcount != 1:
                        raise JobRunnerError("job run is no longer in processing state")
        except BaseException as exc:
            finish_error = exc
            finish_traceback = exc.__traceback__
            if isinstance(exc, Exception):
                # If completion could not be recorded, make one best-effort
                # attempt to persist a failed terminal state on the still-open
                # session. This cannot help while PostgreSQL is unavailable; the
                # next lock owner then recovers the remaining processing row.
                fallback_message = (
                    f"Could not persist {status} state: {type(exc).__name__}: {exc}"
                )[:4000]
                try:
                    with self._connection.transaction():
                        with self._connection.cursor() as cursor:
                            cursor.execute(
                                "UPDATE reporting.job_runs "
                                "SET status = 'failed', finished_at = now(), error_message = %s "
                                "WHERE id = %s AND status = 'processing'",
                                (fallback_message, self.run_id),
                            )
                            if cursor.rowcount != 1:
                                raise JobRunnerError(
                                    "could not persist fallback failed state for the job run"
                                )
                    logger.error(
                        "Terminal state update failed; fallback marked the attempt failed",
                        extra={
                            "job_name": self.job_name,
                            "status": "failed",
                            "target_date": self.target_date.isoformat(),
                        },
                        exc_info=(type(exc), exc, finish_traceback),
                    )
                except Exception as fallback_error:
                    exc.add_note(
                        "Fallback update to failed also did not persist: "
                        f"{type(fallback_error).__name__}: {fallback_error}"
                    )
        finally:
            # Closing the owning PostgreSQL session always releases its session lock,
            # including when a terminal-state write fails. If the database itself
            # is unavailable, the row can remain processing until a later acquire
            # obtains the global lock and recovers abandoned rows.
            self._closed = True
            try:
                self._connection.close()
            except BaseException as close_error:
                if finish_error is None:
                    raise
                finish_error.add_note(
                    f"Closing the PostgreSQL connection also failed: "
                    f"{type(close_error).__name__}: {close_error}"
                )

        if finish_error is not None:
            logger.error(
                "Could not persist terminal job state: %s: %s",
                type(finish_error).__name__,
                finish_error,
                extra={
                    "job_name": self.job_name,
                    "status": "terminal_state_error",
                    "target_date": self.target_date.isoformat(),
                },
                exc_info=(type(finish_error), finish_error, finish_traceback),
            )
            raise finish_error.with_traceback(finish_traceback)

        logger.info(
            "Job state persisted as %s",
            status,
            extra={
                "job_name": self.job_name,
                "status": status,
                "target_date": self.target_date.isoformat(),
            },
        )

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type: Any, exc: BaseException | None, _tb: Any) -> bool:
        if self._closed:
            return False
        if exc is None:
            self.fail("Job exited without an explicit completed state")
        else:
            try:
                self.fail(f"{type(exc).__name__}: {exc}")
            except Exception as state_error:
                exc.add_note(
                    "Additionally, failed-state persistence failed: "
                    f"{type(state_error).__name__}: {state_error}"
                )
        return False


class JobRunner:
    """Create attempts under a global per-job PostgreSQL advisory lock.

    The lock is session-scoped and held by the same connection for the complete
    job lifetime. PostgreSQL releases it automatically if the process/session
    dies, so recovery only marks old nonterminal rows failed after acquiring that
    lock (which proves no live session still owns it).
    """

    def __init__(self, connect: Callable[..., Any] = psycopg.connect) -> None:
        self._connect = connect

    def acquire(self, job_name: str, target_date: date) -> JobRunLease | None:
        """Acquire the global job lock and create an attempt, or return None.

        A previously completed (job_name, target_date) is idempotently skipped.
        Failed and abandoned attempts are retained; a retry gets a new attempt
        number. The advisory lock key is based only on job_name, not target_date.
        """
        _validate_identity(job_name, target_date)
        connection = self._connect(get_reporting_database_url(), autocommit=True)
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT pg_try_advisory_lock(hashtextextended(%s, 0))",
                    (f"nightly-job:{job_name}",),
                )
                acquired = cursor.fetchone()[0]
            if not acquired:
                connection.close()
                return None

            completed_exists = False
            attempt = 0
            run_id: UUID | None = None
            with connection.transaction():
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT 1 FROM reporting.job_runs "
                        "WHERE job_name = %s AND target_date = %s AND status = 'completed' LIMIT 1",
                        (job_name, target_date),
                    )
                    completed_exists = cursor.fetchone() is not None

                    if not completed_exists:
                        # Now that this connection owns the global lock, any remaining
                        # nonterminal rows are abandoned, not live work.
                        cursor.execute(
                            "UPDATE reporting.job_runs "
                            "SET status = 'failed', finished_at = now(), "
                            "error_message = 'Recovered abandoned attempt after acquiring global job lock' "
                            "WHERE job_name = %s AND status IN ('pending', 'processing')",
                            (job_name,),
                        )
                        if cursor.rowcount:
                            logger.info(
                                "Recovered %s abandoned job attempt(s)",
                                cursor.rowcount,
                                extra={
                                    "job_name": job_name,
                                    "status": "recovered",
                                    "target_date": target_date.isoformat(),
                                },
                            )
                        cursor.execute(
                            "SELECT COALESCE(MAX(attempt), 0) + 1 "
                            "FROM reporting.job_runs WHERE job_name = %s AND target_date = %s",
                            (job_name, target_date),
                        )
                        attempt = cursor.fetchone()[0]
                        cursor.execute(
                            "INSERT INTO reporting.job_runs "
                            "(job_name, target_date, attempt, status) "
                            "VALUES (%s, %s, %s, 'pending') RETURNING id",
                            (job_name, target_date, attempt),
                        )
                        run_id = cursor.fetchone()[0]

            if completed_exists:
                self._unlock_and_close(connection, job_name)
                return None

            if run_id is None or attempt < 1:
                raise JobRunnerError("failed to create a job attempt")

            with connection.transaction():
                with connection.cursor() as cursor:
                    cursor.execute(
                        "UPDATE reporting.job_runs SET status = 'processing', started_at = now() "
                        "WHERE id = %s AND status = 'pending'",
                        (run_id,),
                    )
                    if cursor.rowcount != 1:
                        raise JobRunnerError("could not transition the new attempt to processing")
            return JobRunLease(run_id, job_name, target_date, attempt, connection)
        except Exception:
            # If lock acquisition succeeded, closing the session releases it. A
            # committed pending/processing row is recovered safely by the next owner.
            connection.close()
            raise

    @staticmethod
    def _unlock_and_close(connection: Any, job_name: str) -> None:
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT pg_advisory_unlock(hashtextextended(%s, 0))",
                    (f"nightly-job:{job_name}",),
                )
        finally:
            connection.close()
