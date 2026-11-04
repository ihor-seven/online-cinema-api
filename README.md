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

## API: Passwords

### POST /api/v1/accounts/change-password/
Requires `Authorization: Bearer <access_token>`. Changes the password; all refresh tokens are revoked.
```json
{"old_password": "Test1234!", "new_password": "NewPass5678?"}
```
Responses: `200`, `400` wrong old password, `422` weak new password.

### POST /api/v1/accounts/forgot-password/
Sends a reset token (valid for 1 hour) to an active account's email. Always returns `200`.
```json
{"email": "user@example.com"}
```

### POST /api/v1/accounts/reset-password/
Sets a new password using the reset token, without the old password.
```json
{"email": "user@example.com", "token": "<token from email>", "new_password": "NewPass5678?"}
```
Responses: `200`, `400` invalid/expired token, `422` weak password.

## User groups and admin API
Groups: `USER` (basic access), `MODERATOR` (will manage movies), `ADMIN` (all rights).

Create the first admin:
```bash
docker compose exec web python -m src.scripts.create_admin admin@example.com 'Admin1234!'
```

Admin-only endpoints:
- `PATCH /api/v1/admin/users/{user_id}/group/` with `{"group": "MODERATOR"}` changes the user's group.
- `POST /api/v1/admin/users/{user_id}/activate/` activates an account manually.

Responses: `401` not authorized, `403` not an admin, `404` user not found.

## Movies data model
Tables: `movies`, `genres`, `stars`, `directors`, `certifications`
and association tables `movie_genres`, `movie_stars`, `movie_directors`.

- A movie has exactly one certification and many genres, stars and directors.
- `(name, year, time)` is unique for movies; names of genres, stars,
  directors and certifications are unique.

## API: Movie catalog (public)

### GET /api/v1/movies/
Returns a page of movies. All query parameters are optional and can be combined:

| Parameter | Description |
|---|---|
| `page`, `per_page` | Pagination (default 1 and 10, max `per_page` is 20) |
| `year`, `min_year`, `max_year` | Filter by release year |
| `min_imdb`, `max_imdb` | Filter by IMDb rating (0-10) |
| `genre_id` | Only movies of this genre |
| `search` | Search in title, description, stars and directors |
| `sort_by` | `price`, `year`, `imdb`, `votes` (popularity), `name` (default `year`) |
| `order` | `asc` or `desc` (default `desc`) |

Response: `items`, `page`, `per_page`, `total_items`, `total_pages`.

### GET /api/v1/movies/{movie_id}/
Full movie details. `404` if the movie does not exist.

### GET /api/v1/genres/
All genres with the number of movies in each. Use a genre `id` as `genre_id` in the movie list to see its movies.

### Sample data
```bash
docker compose exec web python -m src.scripts.seed_movies
```

## API: Favorites, likes and comments

Endpoints marked 🔒 require `Authorization: Bearer <access_token>`.

### Favorites
- 🔒 `POST /api/v1/movies/{movie_id}/favorite/` adds a movie to favorites (`201`, `409` if already added, `404` unknown movie).
- 🔒 `DELETE /api/v1/movies/{movie_id}/favorite/` removes it (`404` if it is not in favorites).
- 🔒 `GET /api/v1/favorites/` lists favorite movies. Supports the same query parameters as `GET /api/v1/movies/` (pagination, filters, search, sorting).

### Likes and dislikes
- 🔒 `PUT /api/v1/movies/{movie_id}/reaction/` with `{"reaction": "like"}` or `{"reaction": "dislike"}`. One reaction per user and movie: a new value replaces the old one. Returns `{"likes": N, "dislikes": N}`.
- 🔒 `DELETE /api/v1/movies/{movie_id}/reaction/` removes your reaction.
- `GET /api/v1/movies/{movie_id}/reactions/` public counters.

### Comments
- 🔒 `POST /api/v1/movies/{movie_id}/comments/` with `{"text": "..."}` (1-1000 characters).
- `GET /api/v1/movies/{movie_id}/comments/` public, newest first, supports `page` and `per_page`.
- 🔒 `DELETE /api/v1/comments/{comment_id}/` the author can delete their own comment; moderators and admins can delete any (`403` otherwise).

## API: Shopping cart

All cart endpoints require `Authorization: Bearer <access_token>`. Each user has one cart; the same movie cannot be added twice.

- `GET /api/v1/cart/` shows movies (title, price, genres, year), `total_items` and `total_price`.
- `POST /api/v1/cart/items/` with `{"movie_id": 1}` adds a movie (`201`, `404` unknown movie, `409` already in the cart).
- `DELETE /api/v1/cart/items/{movie_id}/` removes one movie (`404` if it is not in the cart).
- `DELETE /api/v1/cart/` clears the cart.
- Admin only: `GET /api/v1/admin/users/{user_id}/cart/` shows the cart of any user.

## API: Orders

All endpoints require `Authorization: Bearer <access_token>`.

- `POST /api/v1/orders/` creates a `pending` order from the cart. Movies that are already purchased or are in another pending order are skipped and listed in `excluded` (`already_purchased` / `pending_order`). Prices are saved in `price_at_order`. `400` if the cart is empty or nothing can be ordered.
- `GET /api/v1/orders/` lists my orders (newest first). Query: `page`, `per_page`, `status` (`pending`, `paid`, `canceled`).
- `GET /api/v1/orders/{order_id}/` shows one of my orders (`404` for other users' orders).
- `POST /api/v1/orders/{order_id}/cancel/` cancels a pending order. Paid orders can only be returned via a refund (`400`).
- `GET /api/v1/purchased/` lists movies from paid orders (same filters, search and sorting as `GET /api/v1/movies/`).
- Admin only: `GET /api/v1/admin/orders/` lists orders of all users. Query: `user_id`, `status`, `date_from`, `date_to` (YYYY-MM-DD), `page`, `per_page`.

Adding an already purchased movie to the cart returns `409`.

## API: Moderator tools

Require `Authorization: Bearer <access_token>` of a user from the `MODERATOR` or `ADMIN` group (`403` for regular users).

### Movies
- `POST /api/v1/moderator/movies/` creates a movie. Certification, genres, stars and directors are given by name; missing ones are created automatically. `(name, year, time)` must be unique (`409`).
- `PATCH /api/v1/moderator/movies/{movie_id}/` partial update: send only the fields to change. Lists (`genres`, `stars`, `directors`) replace the current ones. `meta_score` and `gross` can be `null`.
- `DELETE /api/v1/moderator/movies/{movie_id}/`:
  - `409` if the movie is part of any order;
  - `409` with `carts_count` if the movie is in user carts: repeat with `?force=true` to delete it and remove it from the carts;
  - likes, favorites and comments of the movie are deleted with it.

Example body for creating a movie:
```json
{
  "name": "Dune", "year": 2021, "time": 155, "imdb": 8.0, "votes": 600000,
  "description": "A noble family becomes embroiled in a war for a desert planet.",
  "price": "11.50", "certification": "PG-13",
  "genres": ["Sci-Fi"], "stars": ["Timothée Chalamet"], "directors": ["Denis Villeneuve"]
}
```

### Genres, stars, directors
For each of `genres`, `stars`, `directors`:
- `POST /api/v1/moderator/{genres|stars|directors}/` with `{"name": "..."}`
- `PATCH /api/v1/moderator/{genres|stars|directors}/{id}/` renames
- `DELETE /api/v1/moderator/{genres|stars|directors}/{id}/` (`409` if linked to movies)

Payments are intentionally not part of this project.
