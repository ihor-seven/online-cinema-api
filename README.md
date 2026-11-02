# Online Cinema API

Online cinema REST API built with FastAPI: JWT auth, movie catalog, cart, orders and Stripe payments.

## Tech stack
FastAPI, SQLAlchemy, Alembic, PostgreSQL, Redis, Celery, Docker, Poetry, Pytest

## Run locally
```bash
poetry install
cp .env.example .env
poetry run uvicorn src.main:app --reload
```

## Run with Docker
```bash
cp .env.example .env
docker compose up --build
```
Swagger docs: http://127.0.0.1:8000/docs

## Run tests
```bash
poetry run pytest
```