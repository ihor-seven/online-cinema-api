import math

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session, selectinload

from src.models import Director, Genre, Movie, Star
from src.schemas.movies import MovieFilters, SortOrder


def get_movies_page(db: Session, stmt: Select, filters: MovieFilters) -> dict:
    """Apply filters, search, sorting and pagination to a Movie select."""
    if filters.year is not None:
        stmt = stmt.where(Movie.year == filters.year)
    if filters.min_year is not None:
        stmt = stmt.where(Movie.year >= filters.min_year)
    if filters.max_year is not None:
        stmt = stmt.where(Movie.year <= filters.max_year)
    if filters.min_imdb is not None:
        stmt = stmt.where(Movie.imdb >= filters.min_imdb)
    if filters.max_imdb is not None:
        stmt = stmt.where(Movie.imdb <= filters.max_imdb)
    if filters.genre_id is not None:
        stmt = stmt.where(Movie.genres.any(Genre.id == filters.genre_id))
    if filters.search:
        pattern = f"%{filters.search}%"
        stmt = stmt.where(
            or_(
                Movie.name.ilike(pattern),
                Movie.description.ilike(pattern),
                Movie.stars.any(Star.name.ilike(pattern)),
                Movie.directors.any(Director.name.ilike(pattern)),
            )
        )

    total_items = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0

    column = getattr(Movie, filters.sort_by.value)
    direction = column.asc() if filters.order == SortOrder.ASC else column.desc()
    stmt = (
        stmt.order_by(direction, Movie.id)
        .offset((filters.page - 1) * filters.per_page)
        .limit(filters.per_page)
        .options(selectinload(Movie.genres))
    )

    return {
        "items": db.scalars(stmt).all(),
        "page": filters.page,
        "per_page": filters.per_page,
        "total_items": total_items,
        "total_pages": math.ceil(total_items / filters.per_page),
    }
