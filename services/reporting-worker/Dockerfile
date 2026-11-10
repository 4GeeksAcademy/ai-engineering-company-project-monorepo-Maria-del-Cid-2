FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
RUN pip install --no-cache-dir uv
COPY packages/shared/python /app/packages/shared/python
COPY services/api /app/services/api
COPY data/pipelines /app/data/pipelines
COPY services/reporting-worker /app/services/reporting-worker
RUN uv sync --project /app/services/api --no-dev

WORKDIR /app
