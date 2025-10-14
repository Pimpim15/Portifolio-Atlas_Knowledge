FROM python:3.11-slim

ENV POETRY_VERSION=1.8.3 \
    POETRY_HOME=/opt/poetry \
    POETRY_VIRTUALENVS_CREATE=false \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

RUN pip install --no-cache-dir "poetry==${POETRY_VERSION}" && \
    apt-get update && apt-get install -y --no-install-recommends build-essential && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml poetry.lock* ./
RUN poetry install --no-root --only main

COPY services/__init__.py /app/services/__init__.py
COPY services/api /app/services/api
COPY services/worker /app/services/worker

CMD ["poetry", "run", "python", "services/worker/atlas_worker/run.py"]
