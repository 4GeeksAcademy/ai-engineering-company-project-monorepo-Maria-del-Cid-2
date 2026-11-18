"""PostgreSQL persistence for terminal Incident Analysis task failures."""

from __future__ import annotations

import os
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

import psycopg


class DlqStorageUnavailable(RuntimeError):
    """Raised when the dedicated Celery PostgreSQL store is unavailable."""


def get_celery_database_url() -> str:
    """Return the private DLQ URL, requiring a PostgreSQL URL and TLS."""

    url = os.environ.get("CELERY_DATABASE_URL", "").strip()
    if not url:
        raise DlqStorageUnavailable("CELERY_DATABASE_URL is not configured")
    if not url.startswith(("postgresql://", "postgres://")):
        raise DlqStorageUnavailable("CELERY_DATABASE_URL must use PostgreSQL")
    # libpq honors sslmode=require even if the connection URL did not specify
    # an sslmode query parameter. Never mutate or log the configured secret.
    return url


class IncidentAnalysisDlqRepository:
    """Store only sanitized failure metadata, idempotently by Celery task ID."""

    def __init__(self, connect: Callable[..., Any] = psycopg.connect) -> None:
        self._connect = connect

    def record_failure(
        self,
        *,
        task_id: str,
        task_name: str,
        attempt_count: int,
        exception_type: str,
    ) -> None:
        if not task_id or len(task_id) > 128:
            raise ValueError("Invalid task ID")
        safe_task_name = task_name if task_name == "nexova.incidents.analyze" else "nexova.incidents.analyze"
        safe_exception_type = exception_type if exception_type.isidentifier() else "UnknownError"
        query = (
            "INSERT INTO public.celery_incident_analysis_dlq "
            "(task_id, task_name, failed_at, attempt_count, error_type) "
            "VALUES (%s, %s, %s, %s, %s) "
            "ON CONFLICT (task_id) DO UPDATE SET "
            "task_name = EXCLUDED.task_name, failed_at = EXCLUDED.failed_at, "
            "attempt_count = EXCLUDED.attempt_count, error_type = EXCLUDED.error_type"
        )
        try:
            with self._connect(get_celery_database_url(), sslmode="require") as conn:
                if not conn.pgconn.ssl_in_use:
                    raise DlqStorageUnavailable("DLQ connection is not using TLS")
                with conn.cursor() as cur:
                    cur.execute(
                        query,
                        (
                            task_id,
                            safe_task_name,
                            datetime.now(timezone.utc),
                            max(1, min(attempt_count, 3)),
                            safe_exception_type[:100],
                        ),
                    )
                conn.commit()
        except (DlqStorageUnavailable, ValueError):
            raise
        except psycopg.Error as exc:
            # Do not chain DB errors: drivers may include connection details.
            raise DlqStorageUnavailable("DLQ persistence failed") from None
        except Exception:
            # Do not leak driver/URL details from unexpected connection failures.
            raise DlqStorageUnavailable("DLQ persistence failed") from None
