FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/packages/shared/python/src:/app/services/api

WORKDIR /app
COPY packages/shared/python /app/packages/shared/python
COPY services/api /app/services/api
COPY services/inventory-outbox-worker /app/services/inventory-outbox-worker
RUN pip install --no-cache-dir -e /app/packages/shared/python -e /app/services/api

CMD ["python", "-m", "app.inventory_outbox_worker"]
