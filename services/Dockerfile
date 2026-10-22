FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY services/api/requirements.txt /app/services/api/requirements.txt
COPY packages/shared/python /app/packages/shared/python

RUN cd /app/services/api && uv pip install --system -r requirements.txt

COPY services/api /app/services/api

WORKDIR /app/services/api

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
