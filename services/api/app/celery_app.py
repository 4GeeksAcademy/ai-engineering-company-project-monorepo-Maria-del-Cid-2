"""Celery application configuration for Nexova."""

import os

from celery import Celery

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "nexova",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["app.tasks.test_tasks"],
)

celery_app.conf.update(
    task_track_started=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Europe/Madrid",
    enable_utc=True,
    broker_connection_retry_on_startup=True,
)