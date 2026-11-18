"""Temporary tasks to verify Celery worker execution."""

from app.celery_app import celery_app


@celery_app.task(name="nexova.test.add")
def add(x: int, y: int) -> int:
    """Add two numbers to verify asynchronous task execution."""
    return x + y