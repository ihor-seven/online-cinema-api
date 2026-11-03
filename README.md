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

### POST /api/v1/accounts/activate/
Activates an account with the token sent by email (valid for 24 hours).
```json
{"email": "user@example.com", "token": "<token from email>"}
```
Responses: `200` activated, `400` invalid/expired token or already active.

### POST /api/v1/accounts/resend-activation/
Sends a new activation token (valid for another 24 hours).
```json
{"email": "user@example.com"}
```
Always returns `200` so it does not reveal whether the email is registered.

### Emails in development
Emails are caught by Mailpit: http://localhost:8025

## API: Authentication

### POST /api/v1/accounts/login/
Returns a pair of JWT tokens for an activated account.
```json
{"email": "user@example.com", "password": "Test1234!"}
```
Response: `{"access_token": "...", "refresh_token": "...", "token_type": "bearer"}`.
Access token lives 15 minutes, refresh token 7 days.
Responses: `200`, `401` wrong credentials, `403` account not activated.

### POST /api/v1/accounts/refresh/
Returns a new access token for a valid refresh token.
```json
{"refresh_token": "..."}
```

### POST /api/v1/accounts/logout/
Revokes the refresh token (deletes it from the database).
```json
{"refresh_token": "..."}
```

### GET /api/v1/accounts/me/
Returns the current user. Send header `Authorization: Bearer <access_token>`.