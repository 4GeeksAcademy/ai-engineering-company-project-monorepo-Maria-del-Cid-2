FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/scripts \
    TZ=UTC

WORKDIR /app
COPY services/retention_scheduler.py /app/services/retention_scheduler.py
COPY scripts/retention_manager.py /app/scripts/retention_manager.py
COPY scripts/csv_artifact_lock.py /app/scripts/csv_artifact_lock.py

CMD ["python", "/app/services/retention_scheduler.py"]
