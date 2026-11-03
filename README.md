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

## Database migrations
```bash
docker compose exec web alembic upgrade head
```

## Run tests
```bash
poetry run pytest
```

## API: Accounts

### POST /api/v1/accounts/register/
Registers a new user. The account is inactive until activated.

Request body:
```json
{"email": "user@example.com", "password": "Test1234!"}
```
Password rules: min 8 chars, uppercase, lowercase, digit, special character.

Responses: `201` created, `409` email already exists, `422` validation error.