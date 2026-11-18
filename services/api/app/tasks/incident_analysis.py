"""Celery task for privacy-safe asynchronous incident analysis."""

from __future__ import annotations

import errno
import logging
import os
import re
from pathlib import Path
from typing import Any

from celery import Task

from app.celery_app import celery_app
from app.incidents.analysis import analyze_incidents
from app.incidents.csv_reader import CsvReadError, read_incidents_csv
from app.incidents.task_results import serialize_analysis_result

logger = logging.getLogger(__name__)
_TASK_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")
_TRANSIENT_ERRNOS = {errno.EAGAIN, errno.EIO, errno.ETIMEDOUT, errno.ENOENT}


class IncidentAnalysisTask(Task):
    """Base task with a terminal failure hook, after Celery exhausts retries."""

    abstract = True

    def on_failure(
        self,
        exc: Exception,
        task_id: str,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        einfo: Any,
    ) -> None:
        upload_id = args[0] if args else kwargs.get("upload_id")
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
def analyze_incidents_task(self, upload_id: str) -> dict[str, object]:
    """Analyze an opaque shared-volume CSV reference and return aggregate metrics."""

    if not _TASK_ID_PATTERN.fullmatch(upload_id):
        raise ValueError("Invalid incident analysis input reference")

    input_path = get_incident_upload_dir() / f"{upload_id}.csv"
    try:
        if not input_path.is_file():
            raise FileNotFoundError("Incident analysis input is unavailable")
        rows = read_incidents_csv(input_path)
        if not rows:
            raise CsvReadError("CSV must contain at least one data row")
        result = serialize_analysis_result(analyze_incidents(rows))
    except Exception as exc:
        logger.warning("Incident analysis task failed exception_type=%s", type(exc).__name__)
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

