import enum
import math

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from src.database import get_db
from src.models import Director, Genre, Movie, Star, movie_genres
from src.schemas.movies import (
    GenreWithCountSchema,
    MovieDetailSchema,
    MovieListResponse,
)

router = APIRouter(prefix="/api/v1", tags=["Movies"])


class MovieSortBy(str, enum.Enum):
    PRICE = "price"
    YEAR = "year"
    IMDB = "imdb"
    VOTES = "votes"
    NAME = "name"


class SortOrder(str, enum.Enum):
    ASC = "asc"
    DESC = "desc"


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
    page: int = Query(1, ge=1, description="Page number, starting from 1"),
    per_page: int = Query(10, ge=1, le=20, description="Items per page (max 20)"),
    year: int | None = Query(None, description="Exact release year"),
    min_year: int | None = Query(None, description="Released in or after this year"),
    max_year: int | None = Query(None, description="Released in or before this year"),
    min_imdb: float | None = Query(None, ge=0, le=10, description="Minimum IMDb rating"),
    max_imdb: float | None = Query(None, ge=0, le=10, description="Maximum IMDb rating"),
    genre_id: int | None = Query(None, description="Only movies of this genre"),
    search: str | None = Query(
        None,
        min_length=1,
        description="Text to search in title, description, stars and directors",
    ),
    sort_by: MovieSortBy = Query(MovieSortBy.YEAR, description="Field to sort by"),
    order: SortOrder = Query(SortOrder.DESC, description="Sort direction"),
    db: Session = Depends(get_db),
):
    stmt = select(Movie)

    if year is not None:
        stmt = stmt.where(Movie.year == year)
    if min_year is not None:
        stmt = stmt.where(Movie.year >= min_year)
    if max_year is not None:
        stmt = stmt.where(Movie.year <= max_year)
    if min_imdb is not None:
        stmt = stmt.where(Movie.imdb >= min_imdb)
    if max_imdb is not None:
        stmt = stmt.where(Movie.imdb <= max_imdb)
    if genre_id is not None:
        stmt = stmt.where(Movie.genres.any(Genre.id == genre_id))
    if search:
        pattern = f"%{search}%"
        stmt = stmt.where(
            or_(
                Movie.name.ilike(pattern),
                Movie.description.ilike(pattern),
                Movie.stars.any(Star.name.ilike(pattern)),
                Movie.directors.any(Director.name.ilike(pattern)),
            )
        )

    total_items = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0

    column = getattr(Movie, sort_by.value)
    direction = column.asc() if order == SortOrder.ASC else column.desc()
    stmt = (
        stmt.order_by(direction, Movie.id)
        .offset((page - 1) * per_page)
        .limit(per_page)
        .options(selectinload(Movie.genres))
    )
    items = db.scalars(stmt).all()

    return {
        "items": items,
        "page": page,
        "per_page": per_page,
        "total_items": total_items,
        "total_pages": math.ceil(total_items / per_page),
    }


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
