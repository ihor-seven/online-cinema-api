import pytest

from src.models import Genre, UserGroupEnum

CART = "/api/v1/cart/"
ITEMS = "/api/v1/cart/items/"


def item_url(movie_id):
    return f"/api/v1/cart/items/{movie_id}/"


def movie_ids(response):
    return [item["movie_id"] for item in response.json()["items"]]


def test_add_movie_to_cart(client, create_user, create_movie, auth_headers):
    user = create_user()
    movie = create_movie()

    response = client.post(ITEMS, json={"movie_id": movie.id}, headers=auth_headers(user))

    assert response.status_code == 201
    assert movie_ids(response) == [movie.id]
    assert response.json()["total_items"] == 1


def test_add_same_movie_twice_returns_409(client, create_user, create_movie, auth_headers):
    user = create_user()
    movie = create_movie()
    client.post(ITEMS, json={"movie_id": movie.id}, headers=auth_headers(user))

    response = client.post(ITEMS, json={"movie_id": movie.id}, headers=auth_headers(user))

    assert response.status_code == 409
    assert client.get(CART, headers=auth_headers(user)).json()["total_items"] == 1


def test_add_unknown_movie_returns_404(client, create_user, auth_headers):
    user = create_user()

    response = client.post(ITEMS, json={"movie_id": 9999}, headers=auth_headers(user))

    assert response.status_code == 404


def test_cart_requires_authorization(client, create_movie):
    movie = create_movie()

    assert client.get(CART).status_code in (401, 403)
    assert client.post(ITEMS, json={"movie_id": movie.id}).status_code in (401, 403)
    assert client.delete(CART).status_code in (401, 403)


def test_empty_cart(client, create_user, auth_headers):
    user = create_user()

    response = client.get(CART, headers=auth_headers(user))

    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total_items"] == 0
    assert float(data["total_price"]) == 0


def test_cart_shows_title_price_genres_year_and_total(
    client, db_session, create_user, create_movie, auth_headers
):
    user = create_user()
    first = create_movie(name="Inception", year=2010, price="9.99")
    second = create_movie(name="Pulp Fiction", year=1994, price="12.00")
    first.genres = [Genre(name="Sci-Fi")]
    db_session.commit()
    for movie in (first, second):
        client.post(ITEMS, json={"movie_id": movie.id}, headers=auth_headers(user))

    response = client.get(CART, headers=auth_headers(user))

    data = response.json()
    assert [item["name"] for item in data["items"]] == ["Inception", "Pulp Fiction"]
    inception = data["items"][0]
    assert inception["year"] == 2010
    assert float(inception["price"]) == pytest.approx(9.99)
    assert [g["name"] for g in inception["genres"]] == ["Sci-Fi"]
    assert float(data["total_price"]) == pytest.approx(21.99)
    assert data["total_items"] == 2


def test_remove_movie_from_cart(client, create_user, create_movie, auth_headers):
    user = create_user()
    first = create_movie(name="First")
    second = create_movie(name="Second")
    for movie in (first, second):
        client.post(ITEMS, json={"movie_id": movie.id}, headers=auth_headers(user))

    response = client.delete(item_url(first.id), headers=auth_headers(user))

    assert response.status_code == 200
    assert movie_ids(response) == [second.id]


def test_remove_movie_not_in_cart_returns_404(
    client, create_user, create_movie, auth_headers
):
    user = create_user()
    movie = create_movie()

    response = client.delete(item_url(movie.id), headers=auth_headers(user))

    assert response.status_code == 404


def test_clear_cart(client, create_user, create_movie, auth_headers):
    user = create_user()
    for name in ("First", "Second"):
        movie = create_movie(name=name)
        client.post(ITEMS, json={"movie_id": movie.id}, headers=auth_headers(user))

    response = client.delete(CART, headers=auth_headers(user))

    assert response.status_code == 200
    assert response.json()["items"] == []
    assert client.get(CART, headers=auth_headers(user)).json()["total_items"] == 0


def test_clear_empty_cart_is_ok(client, create_user, auth_headers):
    user = create_user()

    response = client.delete(CART, headers=auth_headers(user))

    assert response.status_code == 200


def test_carts_are_separate_for_each_user(client, create_user, create_movie, auth_headers):
    first = create_user(email="first@example.com")
    second = create_user(email="second@example.com")
    movie = create_movie()
    client.post(ITEMS, json={"movie_id": movie.id}, headers=auth_headers(first))

    response = client.get(CART, headers=auth_headers(second))

    assert response.json()["items"] == []


def test_two_users_can_have_the_same_movie_in_cart(
    client, create_user, create_movie, auth_headers
):
    first = create_user(email="first@example.com")
    second = create_user(email="second@example.com")
    movie = create_movie()

    for user in (first, second):
        response = client.post(ITEMS, json={"movie_id": movie.id}, headers=auth_headers(user))
        assert response.status_code == 201


def test_admin_can_view_user_cart(client, create_user, create_movie, auth_headers):
    admin = create_user(email="admin@example.com", group=UserGroupEnum.ADMIN)
    user = create_user(email="user@example.com")
    movie = create_movie()
    client.post(ITEMS, json={"movie_id": movie.id}, headers=auth_headers(user))

    response = client.get(f"/api/v1/admin/users/{user.id}/cart/", headers=auth_headers(admin))

    assert response.status_code == 200
    assert movie_ids(response) == [movie.id]


def test_regular_user_cannot_view_other_cart(client, create_user, auth_headers):
    first = create_user(email="first@example.com")
    second = create_user(email="second@example.com")

    response = client.get(f"/api/v1/admin/users/{second.id}/cart/", headers=auth_headers(first))

    assert response.status_code == 403


def test_admin_view_cart_of_unknown_user_returns_404(client, create_user, auth_headers):
    admin = create_user(email="admin@example.com", group=UserGroupEnum.ADMIN)

    response = client.get("/api/v1/admin/users/9999/cart/", headers=auth_headers(admin))

    assert response.status_code == 404
    