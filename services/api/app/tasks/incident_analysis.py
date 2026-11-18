"""Celery task for privacy-safe asynchronous incident analysis."""

from __future__ import annotations

import errno
import hashlib
import logging
import os
import re
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from celery import Task
from celery.exceptions import Retry

from app.celery_app import celery_app
from app.incidents.analysis import analyze_incidents
from app.incidents.csv_reader import CsvReadError, read_incidents_csv
from app.incidents.task_results import serialize_analysis_result

logger = logging.getLogger(__name__)
_TASK_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")
_TRANSIENT_ERRNOS = {errno.EAGAIN, errno.EIO, errno.ETIMEDOUT, errno.ENOENT}


def _get_correlation_id(headers: Any) -> str:
    """Return an opaque correlation ID, never a caller-controlled raw header."""

    if isinstance(headers, str):
        return headers if re.fullmatch(r"[0-9a-f]{32}", headers) else "-"
    request = headers
    request_headers = getattr(request, "headers", None)
    if not isinstance(request_headers, Mapping) or "correlation_id" not in request_headers:
        if isinstance(request, Mapping):
            request_headers = request.get("headers")
    if not isinstance(request_headers, Mapping):
        return "-"
    value = request_headers.get("correlation_id")
    return value if isinstance(value, str) and re.fullmatch(r"[0-9a-f]{32}", value) else "-"


class IncidentAnalysisTask(Task):
    """Base task with a terminal failure hook, after Celery exhausts retries."""

    abstract = True

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        started = time.monotonic()
        task_id = self.request.id or "-"
        task_name = self.name or "nexova.incidents.analyze"
        attempt = self.request.retries + 1
        correlation_id = _get_correlation_id(kwargs.get("correlation_id"))
        if correlation_id == "-":
            correlation_id = _get_correlation_id(self.request)
        if correlation_id == "-":
            correlation_id = task_id
        logger.info(
            "event=task_started task_id=%s task_name=%s attempt=%d status=STARTED correlation_id=%s",
            task_id,
            task_name,
            attempt,
            correlation_id,
        )
        try:
            result = super().__call__(*args, **kwargs)
        except Retry:
            logger.warning(
                "event=task_retry task_id=%s task_name=%s attempt=%d status=RETRY duration_ms=%.2f correlation_id=%s",
                task_id,
                task_name,
                attempt,
                (time.monotonic() - started) * 1000,
                correlation_id,
            )
            raise
        except Exception as exc:
            logger.error(
                "event=task_failed task_id=%s task_name=%s attempt=%d status=FAILURE duration_ms=%.2f exception_type=%s correlation_id=%s",
                task_id,
                task_name,
                attempt,
                (time.monotonic() - started) * 1000,
                type(exc).__name__,
                correlation_id,
            )
            raise
        logger.info(
            "event=task_succeeded task_id=%s task_name=%s attempt=%d status=SUCCESS duration_ms=%.2f result=aggregate correlation_id=%s",
            task_id,
            task_name,
            attempt,
            (time.monotonic() - started) * 1000,
            correlation_id,
        )
        return result

    def on_failure(
        self,
        exc: Exception,
        task_id: str,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        einfo: Any,
    ) -> None:
        upload_id = args[0] if args else kwargs.get("upload_id")
        logger.error(
            "event=task_terminal_failure task_id=%s task_name=%s attempt=%d status=FAILURE exception_type=%s correlation_id=%s",
            task_id,
            self.name or "nexova.incidents.analyze",
            self.request.retries + 1,
            type(exc).__name__,
            _get_correlation_id(kwargs.get("correlation_id"))
            if _get_correlation_id(kwargs.get("correlation_id")) != "-"
            else task_id,
        )
        try:
            from app.incidents.dlq import IncidentAnalysisDlqRepository

            IncidentAnalysisDlqRepository().record_failure(
                task_id=task_id,
                task_name=self.name or "nexova.incidents.analyze",
                attempt_count=self.request.retries + 1,
                exception_type=type(exc).__name__,
            )
        except Exception as dlq_exc:
            # Do not log an exception message: DB errors can contain connection data.
            logger.error(
                "Incident analysis DLQ persistence failed exception_type=%s",
                type(dlq_exc).__name__,
            )
        finally:
            if isinstance(upload_id, str) and _TASK_ID_PATTERN.fullmatch(upload_id):
                _remove_input(get_incident_upload_dir() / f"{upload_id}.csv")


def get_incident_upload_dir() -> Path:
    """Return the shared upload directory configured for API and workers."""

    return Path(os.getenv("INCIDENT_ANALYSIS_UPLOAD_DIR", "/var/lib/nexova/incident-analysis"))


def _remove_input(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except Exception:
        logger.warning("Incident analysis input cleanup failed")


@celery_app.task(
    bind=True,
    base=IncidentAnalysisTask,
    name="nexova.incidents.analyze",
    acks_late=True,
    max_retries=2,
)
def analyze_incidents_task(
    self, upload_id: str, correlation_id: str | None = None
) -> dict[str, object]:
    """Analyze an opaque shared-volume CSV reference and return aggregate metrics."""

    if not _TASK_ID_PATTERN.fullmatch(upload_id):
        raise ValueError("Invalid incident analysis input reference")

    input_path = get_incident_upload_dir() / f"{upload_id}.csv"
    try:
        if not input_path.is_file():
            raise FileNotFoundError(
                errno.ENOENT, "Incident analysis input is unavailable"
            )
        rows = read_incidents_csv(input_path)
        if not rows:
            raise CsvReadError("CSV must contain at least one data row")
        result = serialize_analysis_result(analyze_incidents(rows))
    except Exception as exc:
        if _is_transient_failure(exc) and self.request.retries < self.max_retries:
            raise self.retry(
                exc=exc,
                countdown=2**self.request.retries,
                max_retries=self.max_retries,
            )
        raise

    # Preserve the input throughout retries; delete only after a successful
    # terminal execution. Terminal failures are cleaned up by on_failure.
    _remove_input(input_path)
    return result


def _is_transient_failure(exc: Exception) -> bool:
    """Retry only recoverable file/transport errors, not invalid input or bugs."""

    current: BaseException | None = exc
    while current is not None:
        if isinstance(current, (TimeoutError, ConnectionError)):
            return True
        if isinstance(current, OSError) and current.errno in _TRANSIENT_ERRNOS:
            return True
        current = current.__cause__ or current.__context__
    return False

