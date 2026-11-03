from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from src.models import Certification, Director, Genre, Movie, Star


def make_movie(certification, **overrides) -> Movie:
    data = {
        "name": "Inception",
        "year": 2010,
        "time": 148,
        "imdb": 8.8,
        "votes": 2_000_000,
        "description": "A thief who steals secrets through dreams.",
        "price": Decimal("9.99"),
        "certification_id": certification.id,
    }
    data.update(overrides)
    return Movie(**data)


@pytest.fixture
def certification(db_session):
    cert = Certification(name="PG-13")
    db_session.add(cert)
    db_session.commit()
    return cert


def test_movie_gets_uuid_and_optional_fields_are_empty(db_session, certification):
    movie = make_movie(certification)
    db_session.add(movie)
    db_session.commit()

    assert movie.uuid is not None
    assert movie.meta_score is None
    assert movie.gross is None


def test_movie_can_have_many_genres_stars_and_directors(db_session, certification):
    movie = make_movie(certification)
    movie.genres = [Genre(name="Sci-Fi"), Genre(name="Action")]
    movie.stars = [Star(name="Leonardo DiCaprio"), Star(name="Elliot Page")]
    movie.directors = [Director(name="Christopher Nolan")]
    db_session.add(movie)
    db_session.commit()

    saved = db_session.scalar(select(Movie).where(Movie.name == "Inception"))
    assert {g.name for g in saved.genres} == {"Sci-Fi", "Action"}
    assert len(saved.stars) == 2
    assert saved.directors[0].name == "Christopher Nolan"
    assert saved.certification.name == "PG-13"


def test_genre_knows_its_movies(db_session, certification):
    genre = Genre(name="Drama")
    first = make_movie(certification, name="Movie A")
    second = make_movie(certification, name="Movie B")
    first.genres = [genre]
    second.genres = [genre]
    db_session.add_all([first, second])
    db_session.commit()

    assert {m.name for m in genre.movies} == {"Movie A", "Movie B"}


def test_same_name_year_time_is_not_allowed(db_session, certification):
    db_session.add(make_movie(certification))
    db_session.commit()

    db_session.add(make_movie(certification))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_same_name_with_different_year_is_allowed(db_session, certification):
    db_session.add(make_movie(certification))
    db_session.add(make_movie(certification, year=2011))

    db_session.commit()

    assert len(db_session.scalars(select(Movie)).all()) == 2


@pytest.mark.parametrize("model", [Genre, Star, Director, Certification])
def test_names_must_be_unique(db_session, model):
    db_session.add(model(name="Duplicate"))
    db_session.commit()

    db_session.add(model(name="Duplicate"))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_movie_requires_certification(db_session):
    movie = Movie(
        name="No Cert",
        year=2000,
        time=100,
        imdb=5.0,
        votes=10,
        description="desc",
        price=Decimal("1.00"),
    )
    db_session.add(movie)

    with pytest.raises(IntegrityError):
        db_session.commit()
        