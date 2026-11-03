FAVORITES = "/api/v1/favorites/"


def fav_url(movie_id):
    return f"/api/v1/movies/{movie_id}/favorite/"


def names(response):
    return [movie["name"] for movie in response.json()["items"]]


def test_add_to_favorites(client, create_user, create_movie, auth_headers):
    user = create_user()
    movie = create_movie()

    response = client.post(fav_url(movie.id), headers=auth_headers(user))

    assert response.status_code == 201
    listed = client.get(FAVORITES, headers=auth_headers(user))
    assert names(listed) == ["Inception"]


def test_add_same_movie_twice_returns_409(client, create_user, create_movie, auth_headers):
    user = create_user()
    movie = create_movie()
    client.post(fav_url(movie.id), headers=auth_headers(user))

    response = client.post(fav_url(movie.id), headers=auth_headers(user))

    assert response.status_code == 409


def test_add_unknown_movie_returns_404(client, create_user, auth_headers):
    user = create_user()

    response = client.post(fav_url(9999), headers=auth_headers(user))

    assert response.status_code == 404


def test_favorites_require_authorization(client, create_movie):
    movie = create_movie()

    assert client.post(fav_url(movie.id)).status_code in (401, 403)
    assert client.get(FAVORITES).status_code in (401, 403)


def test_remove_from_favorites(client, create_user, create_movie, auth_headers):
    user = create_user()
    movie = create_movie()
    client.post(fav_url(movie.id), headers=auth_headers(user))

    response = client.delete(fav_url(movie.id), headers=auth_headers(user))

    assert response.status_code == 200
    assert names(client.get(FAVORITES, headers=auth_headers(user))) == []


def test_remove_movie_not_in_favorites_returns_404(
    client, create_user, create_movie, auth_headers
):
    user = create_user()
    movie = create_movie()

    response = client.delete(fav_url(movie.id), headers=auth_headers(user))

    assert response.status_code == 404


def test_favorites_are_separate_for_each_user(
    client, create_user, create_movie, auth_headers
):
    first = create_user(email="first@example.com")
    second = create_user(email="second@example.com")
    movie = create_movie()
    client.post(fav_url(movie.id), headers=auth_headers(first))

    response = client.get(FAVORITES, headers=auth_headers(second))

    assert names(response) == []


def test_favorites_support_search_filter_sort_and_pagination(
    client, create_user, create_movie, auth_headers
):
    user = create_user()
    cheap = create_movie(name="Alpha", year=2000, price="5.00", imdb=7.0)
    middle = create_movie(name="Beta", year=2010, price="8.00", imdb=8.0)
    pricey = create_movie(name="Gamma", year=2020, price="12.00", imdb=9.0)
    create_movie(name="Delta", year=2021, price="1.00", imdb=9.5)  # not a favorite
    for movie in (cheap, middle, pricey):
        client.post(fav_url(movie.id), headers=auth_headers(user))
    headers = auth_headers(user)

    assert names(client.get(FAVORITES, params={"search": "beta"}, headers=headers)) == ["Beta"]
    assert names(client.get(FAVORITES, params={"min_imdb": 8}, headers=headers)) == [
        "Gamma",
        "Beta",
    ]
    assert names(
        client.get(FAVORITES, params={"sort_by": "price", "order": "asc"}, headers=headers)
    ) == ["Alpha", "Beta", "Gamma"]

    page = client.get(FAVORITES, params={"per_page": 2}, headers=headers).json()
    assert page["total_items"] == 3
    assert page["total_pages"] == 2
    