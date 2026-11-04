import pytest
from sqlalchemy import func, select

from src.models import (
    Comment,
    Director,
    FavoriteMovie,
    Genre,
    MovieReaction,
    Star,
    UserGroupEnum,
)
from tests.test_orders import make_order

MOVIES = "/api/v1/moderator/movies/"

VALID_MOVIE = {
    "name": "Inception",
    "year": 2010,
    "time": 148,
    "imdb": 8.8,
    "votes": 2_400_000,
    "meta_score": 74,
    "description": "A thief who steals secrets through dreams.",
    "price": "9.99",
    "certification": "PG-13",
    "genres": ["Sci-Fi", "Action"],
    "stars": ["Leonardo DiCaprio"],
    "directors": ["Christopher Nolan"],
}


def movie_url(movie_id):
    return f"{MOVIES}{movie_id}/"


def count(db_session, model):
    return db_session.scalar(select(func.count()).select_from(model))


@pytest.fixture
def moderator_headers(create_user, auth_headers):
    user = create_user(email="mod@example.com", group=UserGroupEnum.MODERATOR)
    return auth_headers(user)


# ---------- access ----------


def test_regular_user_gets_403(client, create_user, auth_headers):
    user = create_user()

    response = client.post(MOVIES, json=VALID_MOVIE, headers=auth_headers(user))

    assert response.status_code == 403


def test_anonymous_is_rejected(client):
    response = client.post(MOVIES, json=VALID_MOVIE)

    assert response.status_code in (401, 403)


def test_admin_can_manage_movies_too(client, create_user, auth_headers):
    admin = create_user(email="admin@example.com", group=UserGroupEnum.ADMIN)

    response = client.post(MOVIES, json=VALID_MOVIE, headers=auth_headers(admin))

    assert response.status_code == 201


# ---------- create ----------


def test_create_movie(client, moderator_headers):
    response = client.post(MOVIES, json=VALID_MOVIE, headers=moderator_headers)

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Inception"
    assert data["certification"]["name"] == "PG-13"
    assert {g["name"] for g in data["genres"]} == {"Sci-Fi", "Action"}
    assert data["stars"][0]["name"] == "Leonardo DiCaprio"
    assert data["directors"][0]["name"] == "Christopher Nolan"
    assert float(data["price"]) == pytest.approx(9.99)
    assert data["uuid"]
    public = client.get(f"/api/v1/movies/{data['id']}/")
    assert public.status_code == 200


def test_create_reuses_existing_genres(client, db_session, moderator_headers):
    client.post(MOVIES, json=VALID_MOVIE, headers=moderator_headers)
    second = {**VALID_MOVIE, "name": "Second", "genres": ["Action", "Drama"]}

    client.post(MOVIES, json=second, headers=moderator_headers)

    assert count(db_session, Genre) == 3


def test_create_removes_duplicate_names_in_lists(client, db_session, moderator_headers):
    body = {**VALID_MOVIE, "genres": ["Action", "Action"]}

    response = client.post(MOVIES, json=body, headers=moderator_headers)

    assert len(response.json()["genres"]) == 1


def test_create_duplicate_movie_returns_409(client, moderator_headers):
    client.post(MOVIES, json=VALID_MOVIE, headers=moderator_headers)

    response = client.post(MOVIES, json=VALID_MOVIE, headers=moderator_headers)

    assert response.status_code == 409


def test_same_name_with_other_year_is_allowed(client, moderator_headers):
    client.post(MOVIES, json=VALID_MOVIE, headers=moderator_headers)

    response = client.post(
        MOVIES, json={**VALID_MOVIE, "year": 2011}, headers=moderator_headers
    )

    assert response.status_code == 201


@pytest.mark.parametrize(
    "override",
    [
        {"imdb": 11},
        {"year": 1700},
        {"name": "   "},
        {"price": "-1"},
        {"price": "9.999"},
        {"time": 0},
        {"certification": ""},
        {"meta_score": 150},
    ],
)
def test_create_with_invalid_data_returns_422(client, moderator_headers, override):
    response = client.post(
        MOVIES, json={**VALID_MOVIE, **override}, headers=moderator_headers
    )

    assert response.status_code == 422


def test_create_without_required_field_returns_422(client, moderator_headers):
    body = {key: value for key, value in VALID_MOVIE.items() if key != "description"}

    response = client.post(MOVIES, json=body, headers=moderator_headers)

    assert response.status_code == 422


# ---------- update ----------


def create_via_api(client, headers, **override):
    response = client.post(MOVIES, json={**VALID_MOVIE, **override}, headers=headers)
    assert response.status_code == 201
    return response.json()


def test_update_changes_only_sent_fields(client, moderator_headers):
    movie = create_via_api(client, moderator_headers)

    response = client.patch(
        movie_url(movie["id"]), json={"price": "5.50"}, headers=moderator_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert float(data["price"]) == pytest.approx(5.5)
    assert data["name"] == "Inception"
    assert len(data["genres"]) == 2


def test_update_replaces_genres_and_keeps_old_genre_records(
    client, db_session, moderator_headers
):
    movie = create_via_api(client, moderator_headers)

    response = client.patch(
        movie_url(movie["id"]), json={"genres": ["Drama"]}, headers=moderator_headers
    )

    assert [g["name"] for g in response.json()["genres"]] == ["Drama"]
    assert count(db_session, Genre) == 3


def test_update_can_change_certification(client, moderator_headers):
    movie = create_via_api(client, moderator_headers)

    response = client.patch(
        movie_url(movie["id"]), json={"certification": "R"}, headers=moderator_headers
    )

    assert response.json()["certification"]["name"] == "R"


def test_update_can_set_meta_score_to_null(client, moderator_headers):
    movie = create_via_api(client, moderator_headers)

    response = client.patch(
        movie_url(movie["id"]), json={"meta_score": None}, headers=moderator_headers
    )

    assert response.status_code == 200
    assert response.json()["meta_score"] is None


def test_update_keeping_same_name_year_time_is_ok(client, moderator_headers):
    movie = create_via_api(client, moderator_headers)

    response = client.patch(
        movie_url(movie["id"]),
        json={"name": "Inception", "description": "New text"},
        headers=moderator_headers,
    )

    assert response.status_code == 200
    assert response.json()["description"] == "New text"


def test_update_to_existing_name_year_time_returns_409(client, moderator_headers):
    create_via_api(client, moderator_headers)
    other = create_via_api(client, moderator_headers, name="Other")

    response = client.patch(
        movie_url(other["id"]), json={"name": "Inception"}, headers=moderator_headers
    )

    assert response.status_code == 409


@pytest.mark.parametrize("body", [{}, {"name": None}, {"imdb": 12}])
def test_update_with_invalid_body_returns_422(client, moderator_headers, body):
    movie = create_via_api(client, moderator_headers)

    response = client.patch(movie_url(movie["id"]), json=body, headers=moderator_headers)

    assert response.status_code == 422


def test_update_unknown_movie_returns_404(client, moderator_headers):
    response = client.patch(
        movie_url(9999), json={"name": "X"}, headers=moderator_headers
    )

    assert response.status_code == 404


def test_regular_user_cannot_update_movie(client, create_user, create_movie, auth_headers):
    movie = create_movie()
    user = create_user()

    response = client.patch(
        movie_url(movie.id), json={"name": "X"}, headers=auth_headers(user)
    )

    assert response.status_code == 403


# ---------- delete ----------


def test_delete_movie(client, create_movie, moderator_headers):
    movie = create_movie()

    response = client.delete(movie_url(movie.id), headers=moderator_headers)

    assert response.status_code == 200
    assert client.get(f"/api/v1/movies/{movie.id}/").status_code == 404


def test_delete_unknown_movie_returns_404(client, moderator_headers):
    response = client.delete(movie_url(9999), headers=moderator_headers)

    assert response.status_code == 404


def test_regular_user_cannot_delete_movie(client, create_user, create_movie, auth_headers):
    movie = create_movie()
    user = create_user()

    response = client.delete(movie_url(movie.id), headers=auth_headers(user))

    assert response.status_code == 403
    assert client.get(f"/api/v1/movies/{movie.id}/").status_code == 200


def test_movie_in_order_cannot_be_deleted(
    client, db_session, create_user, create_movie, moderator_headers
):
    user = create_user()
    movie = create_movie()
    make_order(db_session, user, [movie])

    response = client.delete(movie_url(movie.id), headers=moderator_headers)

    assert response.status_code == 409
    assert client.get(f"/api/v1/movies/{movie.id}/").status_code == 200


def test_movie_in_order_cannot_be_deleted_even_with_force(
    client, db_session, create_user, create_movie, moderator_headers
):
    user = create_user()
    movie = create_movie()
    make_order(db_session, user, [movie])

    response = client.delete(
        movie_url(movie.id), params={"force": True}, headers=moderator_headers
    )

    assert response.status_code == 409


def test_movie_in_cart_returns_warning_and_is_kept(
    client, create_user, create_movie, auth_headers, moderator_headers
):
    user = create_user()
    movie = create_movie()
    client.post(
        "/api/v1/cart/items/", json={"movie_id": movie.id}, headers=auth_headers(user)
    )

    response = client.delete(movie_url(movie.id), headers=moderator_headers)

    assert response.status_code == 409
    assert response.json()["detail"]["carts_count"] == 1
    assert client.get(f"/api/v1/movies/{movie.id}/").status_code == 200


def test_force_delete_removes_movie_from_carts(
    client, create_user, create_movie, auth_headers, moderator_headers
):
    user = create_user()
    movie = create_movie()
    client.post(
        "/api/v1/cart/items/", json={"movie_id": movie.id}, headers=auth_headers(user)
    )

    response = client.delete(
        movie_url(movie.id), params={"force": True}, headers=moderator_headers
    )

    assert response.status_code == 200
    cart = client.get("/api/v1/cart/", headers=auth_headers(user)).json()
    assert cart["items"] == []


def test_delete_removes_comments_favorites_and_reactions(
    client, db_session, create_user, create_movie, auth_headers, moderator_headers
):
    user = create_user()
    headers = auth_headers(user)
    movie = create_movie()
    client.post(f"/api/v1/movies/{movie.id}/comments/", json={"text": "Hi"}, headers=headers)
    client.post(f"/api/v1/movies/{movie.id}/favorite/", headers=headers)
    client.put(
        f"/api/v1/movies/{movie.id}/reaction/", json={"reaction": "like"}, headers=headers
    )

    client.delete(movie_url(movie.id), headers=moderator_headers)

    db_session.expire_all()
    assert count(db_session, Comment) == 0
    assert count(db_session, FavoriteMovie) == 0
    assert count(db_session, MovieReaction) == 0


# ---------- genres, stars, directors ----------

NAMED = [("genres", Genre), ("stars", Star), ("directors", Director)]


@pytest.mark.parametrize(("path", "model"), NAMED)
def test_create_named_item(client, db_session, moderator_headers, path, model):
    response = client.post(
        f"/api/v1/moderator/{path}/", json={"name": " Drama "}, headers=moderator_headers
    )

    assert response.status_code == 201
    assert response.json()["name"] == "Drama"
    assert count(db_session, model) == 1


@pytest.mark.parametrize(("path", "model"), NAMED)
def test_create_duplicate_named_item_returns_409(client, moderator_headers, path, model):
    url = f"/api/v1/moderator/{path}/"
    client.post(url, json={"name": "Drama"}, headers=moderator_headers)

    response = client.post(url, json={"name": "Drama"}, headers=moderator_headers)

    assert response.status_code == 409


@pytest.mark.parametrize(("path", "model"), NAMED)
def test_create_named_item_with_empty_name_returns_422(client, moderator_headers, path, model):
    response = client.post(
        f"/api/v1/moderator/{path}/", json={"name": "  "}, headers=moderator_headers
    )

    assert response.status_code == 422


@pytest.mark.parametrize(("path", "model"), NAMED)
def test_rename_named_item(client, moderator_headers, path, model):
    created = client.post(
        f"/api/v1/moderator/{path}/", json={"name": "Old"}, headers=moderator_headers
    ).json()

    response = client.patch(
        f"/api/v1/moderator/{path}/{created['id']}/",
        json={"name": "New"},
        headers=moderator_headers,
    )

    assert response.status_code == 200
    assert response.json()["name"] == "New"


@pytest.mark.parametrize(("path", "model"), NAMED)
def test_rename_to_existing_name_returns_409(client, moderator_headers, path, model):
    url = f"/api/v1/moderator/{path}/"
    client.post(url, json={"name": "First"}, headers=moderator_headers)
    second = client.post(url, json={"name": "Second"}, headers=moderator_headers).json()

    response = client.patch(
        f"{url}{second['id']}/", json={"name": "First"}, headers=moderator_headers
    )

    assert response.status_code == 409


@pytest.mark.parametrize(("path", "model"), NAMED)
def test_rename_unknown_item_returns_404(client, moderator_headers, path, model):
    response = client.patch(
        f"/api/v1/moderator/{path}/9999/", json={"name": "X"}, headers=moderator_headers
    )

    assert response.status_code == 404


@pytest.mark.parametrize(("path", "model"), NAMED)
def test_delete_unused_named_item(client, db_session, moderator_headers, path, model):
    created = client.post(
        f"/api/v1/moderator/{path}/", json={"name": "Temp"}, headers=moderator_headers
    ).json()

    response = client.delete(
        f"/api/v1/moderator/{path}/{created['id']}/", headers=moderator_headers
    )

    assert response.status_code == 200
    assert count(db_session, model) == 0


@pytest.mark.parametrize(("path", "model"), NAMED)
def test_cannot_delete_named_item_linked_to_movie(
    client, db_session, create_movie, moderator_headers, path, model
):
    movie = create_movie()
    item = model(name="Linked")
    getattr(movie, path).append(item)
    db_session.commit()

    response = client.delete(
        f"/api/v1/moderator/{path}/{item.id}/", headers=moderator_headers
    )

    assert response.status_code == 409
    assert count(db_session, model) == 1


@pytest.mark.parametrize(("path", "model"), NAMED)
def test_delete_unknown_named_item_returns_404(client, moderator_headers, path, model):
    response = client.delete(f"/api/v1/moderator/{path}/9999/", headers=moderator_headers)

    assert response.status_code == 404


@pytest.mark.parametrize(("path", "model"), NAMED)
def test_regular_user_cannot_manage_named_items(
    client, create_user, auth_headers, path, model
):
    user = create_user()

    response = client.post(
        f"/api/v1/moderator/{path}/", json={"name": "X"}, headers=auth_headers(user)
    )

    assert response.status_code == 403
    