"""Celery application configuration for Nexova."""

import os
import logging

from celery import Celery
from celery.signals import after_setup_logger

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")


class _CeleryResultRedactionFilter(logging.Filter):
    """Keep Celery's success log, but never print the task result payload."""

    def filter(self, record: logging.LogRecord) -> bool:
        if record.name == "celery.app.trace" and "succeeded in" in record.getMessage():
            if isinstance(record.args, dict) and "return_value" in record.args:
                safe_args = record.args.copy()
                safe_args["return_value"] = "[redacted]"
                record.args = safe_args
        if record.name == "celery.app.trace" and record.levelno >= logging.ERROR:
            if isinstance(record.args, dict) and "exc" in record.args:
                safe_args = record.args.copy()
                safe_args["exc"] = type(safe_args["exc"]).__name__
                record.args = safe_args
            if record.exc_info:
                record.exc_info = None
        return True


@after_setup_logger.connect
def _redact_celery_task_results(logger: logging.Logger, **_kwargs: object) -> None:
    """Prevent Celery's default trace logger from exposing aggregate payloads."""

    redaction_filter = _CeleryResultRedactionFilter()
    logging.getLogger("celery.app.trace").addFilter(redaction_filter)
    for handler in logger.handlers:
        handler.addFilter(redaction_filter)

celery_app = Celery(
    "nexova",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["app.tasks.test_tasks", "app.tasks.incident_analysis"],
)

celery_app.conf.update(
    task_track_started=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Europe/Madrid",
    enable_utc=True,
    broker_connection_retry_on_startup=True,
    result_expires=3600,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_send_task_events=True,
    task_send_sent_event=True,
    task_remote_tracebacks=False,
    task_store_errors_even_if_ignored=True,
    task_annotations={"*": {"throws": (Exception,)}},
)