from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from src.database import get_db
from src.models import Genre, Movie, movie_genres
from src.schemas.movies import (
    GenreWithCountSchema,
    MovieDetailSchema,
    MovieFilters,
    MovieListResponse,
)
from src.services.movies import get_movies_page

router = APIRouter(prefix="/api/v1", tags=["Movies"])


@router.get(
    "/movies/",
    response_model=MovieListResponse,
    summary="Browse the movie catalog",
    description=(
        "Returns a page of movies. All filters are optional and can be "
        "combined. `search` looks in the movie title, description and in "
        "the names of stars and directors. `votes` is used as popularity. "
        "To show the movies of a genre, pass its `genre_id`."
    ),
    responses={422: {"description": "Invalid query parameters"}},
)
def list_movies(
    filters: Annotated[MovieFilters, Query()],
    db: Session = Depends(get_db),
):
    return get_movies_page(db, select(Movie), filters)


@router.get(
    "/movies/{movie_id}/",
    response_model=MovieDetailSchema,
    summary="Get movie details",
    description=(
        "Returns the full description of a movie: certification, genres, "
        "stars, directors, rating, price and other fields."
    ),
    responses={404: {"description": "Movie not found"}},
)
def get_movie(movie_id: int, db: Session = Depends(get_db)):
    stmt = (
        select(Movie)
        .where(Movie.id == movie_id)
        .options(
            selectinload(Movie.genres),
            selectinload(Movie.stars),
            selectinload(Movie.directors),
            selectinload(Movie.certification),
        )
    )
    movie = db.scalar(stmt)
    if movie is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movie with the given ID was not found.",
        )
    return movie


@router.get(
    "/genres/",
    response_model=list[GenreWithCountSchema],
    summary="List genres with the number of movies",
    description=(
        "Returns all genres sorted by name with the count of movies in each. "
        "Use a genre `id` as `genre_id` in `GET /movies/` to see its movies."
    ),
)
def list_genres(db: Session = Depends(get_db)):
    stmt = (
        select(
            Genre.id,
            Genre.name,
            func.count(movie_genres.c.movie_id).label("movie_count"),
        )
        .outerjoin(movie_genres, movie_genres.c.genre_id == Genre.id)
        .group_by(Genre.id, Genre.name)
        .order_by(Genre.name)
    )
    return [
        {"id": row.id, "name": row.name, "movie_count": row.movie_count}
        for row in db.execute(stmt)
    ]
