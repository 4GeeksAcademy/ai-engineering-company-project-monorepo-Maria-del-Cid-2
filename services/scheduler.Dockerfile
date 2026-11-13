FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/scripts \
    TZ=UTC

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
RUN pip install --no-cache-dir "psycopg[binary]>=3.2,<4" "prefect>=3,<4"

COPY services/job_runner.py /app/services/job_runner.py
COPY services/nightly_scheduler.py /app/services/nightly_scheduler.py
COPY scripts/nightly_export.py /app/scripts/nightly_export.py
COPY scripts/csv_artifact_lock.py /app/scripts/csv_artifact_lock.py
COPY data/pipelines /app/data/pipelines

RUN mkdir -p /var/lib/nightly-export

CMD ["python", "/app/services/nightly_scheduler.py"]