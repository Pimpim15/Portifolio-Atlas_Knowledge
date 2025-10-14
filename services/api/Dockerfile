FROM python:3.11-slim AS base

ENV POETRY_VERSION=1.8.3 \
    POETRY_HOME=/opt/poetry \
    POETRY_VIRTUALENVS_CREATE=false \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

RUN pip install --no-cache-dir "poetry==${POETRY_VERSION}" && \
    apt-get update && apt-get install -y --no-install-recommends \
      build-essential libpq-dev && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml poetry.lock* ./
RUN poetry install --no-root --only main

COPY services/__init__.py /app/services/__init__.py
COPY services/api /app/services/api

ENV UVICORN_HOST=0.0.0.0 \
    UVICORN_PORT=8000

CMD ["poetry", "run", "uvicorn", "services.api.atlas_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
