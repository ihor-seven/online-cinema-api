from decimal import Decimal

import pytest

from src.models import Certification, Director, Genre, Movie, Star

MOVIES_URL = "/api/v1/movies/"
GENRES_URL = "/api/v1/genres/"


@pytest.fixture
def catalog(db_session):
    action = Genre(name="Action")
    drama = Genre(name="Drama")
    scifi = Genre(name="Sci-Fi")
    western = Genre(name="Western")
    pg13 = Certification(name="PG-13")
    r_rated = Certification(name="R")
    nolan = Director(name="Christopher Nolan")
    tarantino = Director(name="Quentin Tarantino")
    leo = Star(name="Leonardo DiCaprio")
    travolta = Star(name="John Travolta")

    inception = Movie(
        name="Inception", year=2010, time=148, imdb=8.8, votes=2_400_000,
        description="A thief who steals secrets through dreams.",
        price=Decimal("9.99"), certification=pg13,
        genres=[scifi, action], directors=[nolan], stars=[leo],
    )
    pulp = Movie(
        name="Pulp Fiction", year=1994, time=154, imdb=8.9, votes=2_100_000,
        description="Intertwined stories of crime in Los Angeles.",
        price=Decimal("7.50"), certification=r_rated,
        genres=[drama], directors=[tarantino], stars=[travolta],
    )
    dark = Movie(
        name="The Dark Knight", year=2008, time=152, imdb=9.0, votes=2_700_000,
        description="Batman faces the Joker.",
        price=Decimal("12.00"), certification=pg13,
        genres=[action, drama], directors=[nolan], stars=[],
    )
    db_session.add_all([inception, pulp, dark, western])
    db_session.commit()
    return {"inception": inception, "pulp": pulp, "dark": dark, "action": action}


def names(response):
    return [movie["name"] for movie in response.json()["items"]]


def test_list_returns_movies_with_pagination_info(client, catalog):
    response = client.get(MOVIES_URL)

    assert response.status_code == 200
    data = response.json()
    assert data["total_items"] == 3
    assert data["total_pages"] == 1
    assert data["page"] == 1
    assert len(data["items"]) == 3


def test_list_is_public_and_sorted_by_year_desc_by_default(client, catalog):
    response = client.get(MOVIES_URL)

    assert names(response) == ["Inception", "The Dark Knight", "Pulp Fiction"]


def test_pagination_splits_results_into_pages(client, catalog):
    first = client.get(MOVIES_URL, params={"per_page": 2, "page": 1})
    second = client.get(MOVIES_URL, params={"per_page": 2, "page": 2})

    assert len(first.json()["items"]) == 2
    assert first.json()["total_pages"] == 2
    assert names(second) == ["Pulp Fiction"]


def test_page_beyond_last_returns_empty_list(client, catalog):
    response = client.get(MOVIES_URL, params={"page": 5})

    assert response.status_code == 200
    assert response.json()["items"] == []


@pytest.mark.parametrize(
    "params",
    [{"page": 0}, {"per_page": 0}, {"per_page": 21}, {"sort_by": "color"}, {"min_imdb": 11}],
)
def test_invalid_query_params_return_422(client, catalog, params):
    response = client.get(MOVIES_URL, params=params)

    assert response.status_code == 422


def test_filter_by_year(client, catalog):
    response = client.get(MOVIES_URL, params={"year": 1994})

    assert names(response) == ["Pulp Fiction"]


def test_filter_by_year_range(client, catalog):
    response = client.get(MOVIES_URL, params={"min_year": 2000, "max_year": 2009})

    assert names(response) == ["The Dark Knight"]


def test_filter_by_imdb_rating(client, catalog):
    response = client.get(MOVIES_URL, params={"min_imdb": 8.9})

    assert names(response) == ["The Dark Knight", "Pulp Fiction"]


def test_filter_by_genre(client, catalog):
    response = client.get(MOVIES_URL, params={"genre_id": catalog["action"].id})

    assert names(response) == ["Inception", "The Dark Knight"]


def test_filters_can_be_combined(client, catalog):
    response = client.get(
        MOVIES_URL, params={"genre_id": catalog["action"].id, "min_imdb": 8.9}
    )

    assert names(response) == ["The Dark Knight"]


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("inception", ["Inception"]),
        ("nolan", ["Inception", "The Dark Knight"]),
        ("travolta", ["Pulp Fiction"]),
        ("joker", ["The Dark Knight"]),
        ("nothing-like-this", []),
    ],
)
def test_search_by_title_description_star_and_director(
    client, catalog, query, expected
):
    response = client.get(MOVIES_URL, params={"search": query})

    assert names(response) == expected


def test_sort_by_price_ascending(client, catalog):
    response = client.get(MOVIES_URL, params={"sort_by": "price", "order": "asc"})

    assert names(response) == ["Pulp Fiction", "Inception", "The Dark Knight"]


def test_sort_by_votes_descending_means_popularity(client, catalog):
    response = client.get(MOVIES_URL, params={"sort_by": "votes", "order": "desc"})

    assert names(response) == ["The Dark Knight", "Inception", "Pulp Fiction"]


def test_get_movie_returns_full_details(client, catalog):
    movie_id = catalog["inception"].id

    response = client.get(f"{MOVIES_URL}{movie_id}/")

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Inception"
    assert data["certification"]["name"] == "PG-13"
    assert {g["name"] for g in data["genres"]} == {"Sci-Fi", "Action"}
    assert data["stars"][0]["name"] == "Leonardo DiCaprio"
    assert data["directors"][0]["name"] == "Christopher Nolan"
    assert float(data["price"]) == 9.99
    assert data["meta_score"] is None


def test_get_unknown_movie_returns_404(client, catalog):
    response = client.get(f"{MOVIES_URL}9999/")

    assert response.status_code == 404


def test_genres_list_has_movie_counts(client, catalog):
    response = client.get(GENRES_URL)

    assert response.status_code == 200
    counts = {genre["name"]: genre["movie_count"] for genre in response.json()}
    assert counts == {"Action": 2, "Drama": 2, "Sci-Fi": 1, "Western": 0}
    