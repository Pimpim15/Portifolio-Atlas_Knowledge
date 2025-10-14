SHELL := /bin/bash

.PHONY: bootstrap dev stop lint test format migrate reindex bench seed

bootstrap:
	poetry install
	npm --prefix services/frontend install
	pre-commit install

dev:
	docker compose -f infra/docker-compose.yml up --build

stop:
	docker compose -f infra/docker-compose.yml down

lint:
	poetry run ruff check services/api/atlas_api
	poetry run mypy services/api/atlas_api
	npm --prefix services/frontend run lint

format:
	poetry run ruff format services/api/atlas_api
	npm --prefix services/frontend run format

test:
	poetry run pytest services/api/tests --cov=atlas_api --cov-report=term-missing

migrate:
	poetry run alembic -c services/api/alembic.ini upgrade head

reindex:
	poetry run python services/api/scripts/reindex.py

bench:
	poetry run locust -f bench/locustfile.py

seed:
	poetry run python scripts/seed.py
