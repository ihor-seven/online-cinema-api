# Online Cinema API

![CI](https://github.com/ihor-seven/online-cinema-api/actions/workflows/ci.yml/badge.svg)

REST API of an online cinema built with FastAPI: registration with email activation, JWT authentication, user roles, a movie catalog with search and filters, favorites, likes and comments, a shopping cart, orders and moderator tools.

## Features

1. **Registration and activation**: sign up by email, activation link/token valid for 24 hours, resending the token.
2. **Authentication**: login and logout with JWT (access + refresh tokens), refreshing the access token.
3. **Passwords and roles**: change and reset password with email, password complexity validation, groups `USER`, `MODERATOR`, `ADMIN`, admin tools (change group, activate account manually).
4. **Movie catalog**: pagination, filters (year, IMDb rating, genre), search (title, description, stars, directors), sorting, genres with movie counts.
5. **Favorites, likes and comments**: favorites list with the same search, filters and sorting, one like/dislike per user and movie, comments.
6. **Shopping cart**: add, view, remove, clear; the same movie cannot be added twice or after purchase.
7. **Orders**: create an order from the cart (purchased and already ordered movies are skipped with a notice), price snapshot, cancel, order history, purchased movies, admin view with filters.
8. **Moderator tools**: create, update and delete movies, genres, stars and directors; a movie that is part of an order cannot be deleted.

Infrastructure: Docker Compose, Poetry, Alembic migrations, Celery + Redis + celery-beat (cleanup of expired tokens), GitHub Actions CI, protected API documentation, tests with coverage.

> Online payments are intentionally not part of this project: the orders feature covers the purchase flow up to the `pending` / `canceled` states.

## Tech stack

Python 3.14, FastAPI, SQLAlchemy 2, Alembic, PostgreSQL, Pydantic, JWT (PyJWT), bcrypt, Celery, Redis, Mailpit (development mailbox), Docker Compose, Poetry, Pytest + pytest-cov, black, flake8, mypy, GitHub Actions.

## Getting started

Requirements: Docker with Docker Compose.

```bash
git clone https://github.com/ihor-seven/online-cinema-api.git
cd online-cinema-api

cp .env.example .env
# put a random value into SECRET_KEY, for example: openssl rand -hex 32

docker compose up --build -d
docker compose exec web alembic upgrade head
```

Create the first admin and (optionally) load sample movies:

```bash
docker compose exec web python -m src.scripts.create_admin admin@example.com 'Admin1234!'
docker compose exec web python -m src.scripts.seed_movies
```

Services:

| Service | URL / purpose |
|---|---|
| API | http://127.0.0.1:8000 |
| Swagger UI | http://127.0.0.1:8000/docs (protected, see below) |
| Mailpit (emails sent by the app) | http://localhost:8025 |
| PostgreSQL | `localhost:5432` |
| Redis, Celery worker, Celery beat | run in Docker Compose |

### Environment variables

Copy `.env.example` to `.env` and adjust:

| Variable | Description |
|---|---|
| `APP_NAME`, `DEBUG` | Application title and debug mode |
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_HOST`, `POSTGRES_PORT` | Database connection |
| `SECRET_KEY` | Secret for signing JWT tokens (required) |
| `SMTP_HOST`, `SMTP_PORT`, `EMAIL_FROM` | Mail server (Mailpit in development) |
| `REDIS_URL` | Redis address used by Celery |
| `TOKEN_CLEANUP_INTERVAL_SECONDS` | How often expired tokens are deleted (default 3600) |

## API documentation (protected)

Swagger UI: `/docs`, ReDoc: `/redoc`, OpenAPI schema: `/openapi.json`.

The documentation is visible only to authorized users: the browser asks for the **email and password** (HTTP Basic) of any active account, for example the admin created above. To call protected endpoints from Swagger, log in via `POST /api/v1/accounts/login/` and press **Authorize** with the `access_token`.

Every endpoint is described in Swagger: parameters, request bodies and all possible responses.

## Endpoints overview

Endpoints marked 🔒 require `Authorization: Bearer <access_token>`.

### Accounts and authentication
| Method and path | Description |
|---|---|
| `POST /api/v1/accounts/register/` | Register; the account is inactive until activated. Password: 8-72 bytes, upper and lower case letters, a digit and a special character |
| `POST /api/v1/accounts/activate/` | Activate with `{"email", "token"}` from the email (valid 24 hours) |
| `POST /api/v1/accounts/resend-activation/` | Send a new activation token (always returns `200`) |
| `POST /api/v1/accounts/login/` | Get `access_token` (15 min) and `refresh_token` (7 days) |
| `POST /api/v1/accounts/refresh/` | Get a new access token with a refresh token |
| `POST /api/v1/accounts/logout/` | Revoke the refresh token |
| `GET /api/v1/accounts/me/` 🔒 | Current user |
| `POST /api/v1/accounts/change-password/` 🔒 | Change password with the old one (revokes refresh tokens) |
| `POST /api/v1/accounts/forgot-password/` | Send a reset token by email (valid 1 hour) |
| `POST /api/v1/accounts/reset-password/` | Set a new password with the reset token |

### Movies (public)
| Method and path | Description |
|---|---|
| `GET /api/v1/movies/` | Catalog. Query: `page`, `per_page` (max 20), `year`, `min_year`, `max_year`, `min_imdb`, `max_imdb`, `genre_id`, `search`, `sort_by` (`price`, `year`, `imdb`, `votes`, `name`), `order` (`asc`, `desc`) |
| `GET /api/v1/movies/{movie_id}/` | Movie details |
| `GET /api/v1/genres/` | Genres with the number of movies |
| `GET /api/v1/movies/{movie_id}/reactions/` | Number of likes and dislikes |
| `GET /api/v1/movies/{movie_id}/comments/` | Comments, newest first |

### Favorites, likes and comments
| Method and path | Description |
|---|---|
| `POST /api/v1/movies/{movie_id}/favorite/` 🔒 | Add to favorites |
| `DELETE /api/v1/movies/{movie_id}/favorite/` 🔒 | Remove from favorites |
| `GET /api/v1/favorites/` 🔒 | Favorites with the same query parameters as the catalog |
| `PUT /api/v1/movies/{movie_id}/reaction/` 🔒 | `{"reaction": "like" or "dislike"}` |
| `DELETE /api/v1/movies/{movie_id}/reaction/` 🔒 | Remove my reaction |
| `POST /api/v1/movies/{movie_id}/comments/` 🔒 | `{"text": "..."}` (1-1000 characters) |
| `DELETE /api/v1/comments/{comment_id}/` 🔒 | Author, moderator or admin |

### Cart and orders
| Method and path | Description |
|---|---|
| `GET /api/v1/cart/` 🔒 | Cart with title, price, genres, year, total |
| `POST /api/v1/cart/items/` 🔒 | `{"movie_id": 1}`; `409` if already in the cart or already purchased |
| `DELETE /api/v1/cart/items/{movie_id}/` 🔒 | Remove a movie |
| `DELETE /api/v1/cart/` 🔒 | Clear the cart |
| `POST /api/v1/orders/` 🔒 | Create an order from the cart. Skipped movies are listed in `excluded` (`already_purchased`, `pending_order`) |
| `GET /api/v1/orders/` 🔒 | My orders (`page`, `per_page`, `status`) |
| `GET /api/v1/orders/{order_id}/` 🔒 | One of my orders |
| `POST /api/v1/orders/{order_id}/cancel/` 🔒 | Cancel a pending order (a paid order can only be refunded) |
| `GET /api/v1/purchased/` 🔒 | Movies from paid orders (same query as the catalog) |

### Moderator tools (MODERATOR and ADMIN)
| Method and path | Description |
|---|---|
| `POST /api/v1/moderator/movies/` 🔒 | Create a movie. Certification, genres, stars and directors are given by name and created if missing |
| `PATCH /api/v1/moderator/movies/{movie_id}/` 🔒 | Partial update |
| `DELETE /api/v1/moderator/movies/{movie_id}/` 🔒 | `409` if the movie is in orders; `409` with `carts_count` if it is in carts, repeat with `?force=true` |
| `POST`, `PATCH`, `DELETE /api/v1/moderator/{genres,stars,directors}/` 🔒 | Manage genres, stars and directors (`409` if linked to movies) |

### Admin tools (ADMIN)
| Method and path | Description |
|---|---|
| `PATCH /api/v1/admin/users/{user_id}/group/` 🔒 | `{"group": "USER", "MODERATOR" or "ADMIN"}` |
| `POST /api/v1/admin/users/{user_id}/activate/` 🔒 | Activate an account manually |
| `GET /api/v1/admin/users/{user_id}/cart/` 🔒 | View the cart of any user |
| `GET /api/v1/admin/orders/` 🔒 | All orders. Filters: `user_id`, `status`, `date_from`, `date_to` |

## Background tasks

Celery worker, Celery beat and Redis run in Docker Compose. The task `src.tasks.delete_expired_tokens` runs on a schedule and deletes expired activation tokens, password reset tokens and refresh tokens. A user whose activation token expired can request a new one through `resend-activation`.

```bash
docker compose logs -f celery_worker
```

## Tests and code quality

Tests use an in-memory SQLite database, so neither Docker nor PostgreSQL is needed:

```bash
poetry install
cp .env.example .env
poetry run pytest --cov --cov-report=term-missing
```

The test suite covers unit tests (validation, security helpers, cleanup logic), integration tests (endpoints with the database, JWT workflow) and functional scenarios (registration, activation, login, catalog filtering, cart, orders, moderation). Coverage is measured with `pytest-cov`.

Code quality checks (the same ones run in CI):

```bash
poetry run black --check .
poetry run flake8 src tests
poetry run mypy src
```

GitHub Actions runs these checks and the tests on every push to `main` and on every Pull Request.

## Database migrations

```bash
docker compose exec web alembic upgrade head
docker compose exec web alembic revision --autogenerate -m "describe the change"
```

## Project structure

```
src/
  models/       SQLAlchemy models (accounts, movies, interactions, cart, orders)
  schemas/      Pydantic request and response schemas
  routes/       API endpoints
  services/     Business logic (emails, tokens, catalog queries, cart, orders, cleanup)
  scripts/      create_admin, seed_movies
  config.py, database.py, security.py, dependencies.py
  celery_app.py, tasks.py, main.py
alembic/        Database migrations
tests/          Pytest test suite
docker-compose.yml, Dockerfile, pyproject.toml
.github/workflows/ci.yml
```

## Development workflow

Every feature was developed in its own branch (`feature/user-registration`, `feature/jwt-auth`, `feature/shopping-cart`, ...) with small commits, tests and documentation, and merged through a Pull Request checked by CI.