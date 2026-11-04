from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models import Movie


def get_or_create_by_name(db: Session, model, name: str):
    item = db.scalar(select(model).where(model.name == name))
    if item is None:
        item = model(name=name)
        db.add(item)
        db.flush()
    return item


def resolve_names(db: Session, model, names: list[str]) -> list:
    unique_names = list(dict.fromkeys(names))  # remove duplicates, keep order
    return [get_or_create_by_name(db, model, name) for name in unique_names]


def movie_exists(
    db: Session, name: str, year: int, time: int, exclude_id: int | None = None
) -> bool:
    stmt = select(Movie.id).where(
        Movie.name == name, Movie.year == year, Movie.time == time
    )
    if exclude_id is not None:
        stmt = stmt.where(Movie.id != exclude_id)
    return db.scalar(stmt) is not None
