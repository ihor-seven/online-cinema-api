from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from src.database import get_db
from src.dependencies import require_groups
from src.models import (
    CartItem,
    Certification,
    Comment,
    Director,
    FavoriteMovie,
    Genre,
    Movie,
    MovieReaction,
    OrderItem,
    Star,
    UserGroupEnum,
)
from src.schemas.accounts import MessageResponse
from src.schemas.moderator import (
    MovieCreateRequest,
    MovieUpdateRequest,
    NamedItemRequest,
)
from src.schemas.movies import MovieDetailSchema, NamedItemSchema
from src.services.movie_management import (
    get_or_create_by_name,
    movie_exists,
    resolve_names,
)

router = APIRouter(
    prefix="/api/v1/moderator",
    tags=["Moderator"],
    dependencies=[
        Depends(require_groups(UserGroupEnum.MODERATOR, UserGroupEnum.ADMIN))
    ],
)

ACCESS_ERRORS = {
    401: {"description": "Missing or invalid access token"},
    403: {"description": "Only moderators and admins can do this"},
}

SIMPLE_MOVIE_FIELDS = (
    "name", "year", "time", "imdb", "votes",
    "meta_score", "gross", "description", "price",
)  # fmt: skip


def _get_movie_or_404(db: Session, movie_id: int) -> Movie:
    movie = db.get(Movie, movie_id)
    if movie is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movie with the given ID was not found.",
        )
    return movie


def _count(db: Session, model, column, value) -> int:
    stmt = select(func.count()).select_from(model).where(column == value)
    return db.scalar(stmt) or 0


# ---------- Movies ----------


@router.post(
    "/movies/",
    response_model=MovieDetailSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Create a movie",
    description=(
        "Creates a movie. Certification, genres, stars and directors are "
        "given by name: the ones that do not exist yet are created "
        "automatically. The combination of name, year and duration must be unique."
    ),
    responses={
        **ACCESS_ERRORS,
        409: {"description": "A movie with this name, year and duration exists"},
        422: {"description": "Invalid data"},
    },
)
def create_movie(data: MovieCreateRequest, db: Session = Depends(get_db)):
    if movie_exists(db, data.name, data.year, data.time):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A movie with this name, year and duration already exists.",
        )

    certification = get_or_create_by_name(db, Certification, data.certification)
    movie = Movie(
        name=data.name,
        year=data.year,
        time=data.time,
        imdb=data.imdb,
        votes=data.votes,
        meta_score=data.meta_score,
        gross=data.gross,
        description=data.description,
        price=data.price,
        certification_id=certification.id,
    )
    movie.genres = resolve_names(db, Genre, data.genres)
    movie.stars = resolve_names(db, Star, data.stars)
    movie.directors = resolve_names(db, Director, data.directors)

    db.add(movie)
    db.commit()
    db.refresh(movie)
    return movie


@router.patch(
    "/movies/{movie_id}/",
    response_model=MovieDetailSchema,
    summary="Update a movie",
    description=(
        "Partial update: send only the fields you want to change. If `genres`, "
        "`stars` or `directors` are sent, they replace the current list. "
        "`meta_score` and `gross` can be set to `null`."
    ),
    responses={
        **ACCESS_ERRORS,
        404: {"description": "Movie not found"},
        409: {"description": "A movie with this name, year and duration exists"},
        422: {"description": "Invalid data or nothing to update"},
    },
)
def update_movie(
    movie_id: int, data: MovieUpdateRequest, db: Session = Depends(get_db)
):
    movie = _get_movie_or_404(db, movie_id)
    changes = data.model_dump(exclude_unset=True)

    new_name = changes.get("name", movie.name)
    new_year = changes.get("year", movie.year)
    new_time = changes.get("time", movie.time)
    if movie_exists(db, new_name, new_year, new_time, exclude_id=movie.id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A movie with this name, year and duration already exists.",
        )

    for field in SIMPLE_MOVIE_FIELDS:
        if field in changes:
            setattr(movie, field, changes[field])
    if "certification" in changes:
        movie.certification_id = get_or_create_by_name(
            db, Certification, changes["certification"]
        ).id
    if "genres" in changes:
        movie.genres = resolve_names(db, Genre, changes["genres"])
    if "stars" in changes:
        movie.stars = resolve_names(db, Star, changes["stars"])
    if "directors" in changes:
        movie.directors = resolve_names(db, Director, changes["directors"])

    db.commit()
    db.refresh(movie)
    return movie


@router.delete(
    "/movies/{movie_id}/",
    response_model=MessageResponse,
    summary="Delete a movie",
    description=(
        "A movie that is part of any order cannot be deleted. If the movie "
        "is in carts of users, the request is rejected with a warning that "
        "contains `carts_count`; repeat it with `force=true` to delete the "
        "movie and remove it from those carts. Likes, favorites and comments "
        "of the movie are deleted together with it."
    ),
    responses={
        **ACCESS_ERRORS,
        404: {"description": "Movie not found"},
        409: {"description": "The movie is in orders, or in carts and no `force`"},
    },
)
def delete_movie(
    movie_id: int,
    force: bool = Query(False, description="Delete even if the movie is in carts"),
    db: Session = Depends(get_db),
):
    movie = _get_movie_or_404(db, movie_id)

    if _count(db, OrderItem, OrderItem.movie_id, movie_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The movie is part of existing orders and cannot be deleted.",
        )

    carts_count = _count(db, CartItem, CartItem.movie_id, movie_id)
    if carts_count and not force:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": (
                    f"The movie is in {carts_count} user cart(s). Repeat the "
                    "request with force=true to delete it anyway."
                ),
                "carts_count": carts_count,
            },
        )

    for model in (CartItem, FavoriteMovie, MovieReaction, Comment):
        db.execute(delete(model).where(model.movie_id == movie_id))
    db.delete(movie)
    db.commit()
    return MessageResponse(message="Movie deleted.")


# ---------- Genres, stars and directors ----------


def _register_named_crud(model, path: str, label: str) -> None:
    """Create POST, PATCH and DELETE endpoints for a model with a unique name."""

    @router.post(
        f"/{path}/",
        response_model=NamedItemSchema,
        status_code=status.HTTP_201_CREATED,
        summary=f"Create a {label}",
        responses={
            **ACCESS_ERRORS,
            409: {"description": f"A {label} with this name already exists"},
        },
        operation_id=f"create_{label}",
    )
    def create_item(data: NamedItemRequest, db: Session = Depends(get_db)):
        if db.scalar(select(model).where(model.name == data.name)) is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A {label} with this name already exists.",
            )
        item = model(name=data.name)
        db.add(item)
        db.commit()
        db.refresh(item)
        return item

    @router.patch(
        f"/{path}/{{item_id}}/",
        response_model=NamedItemSchema,
        summary=f"Rename a {label}",
        responses={
            **ACCESS_ERRORS,
            404: {"description": f"The {label} was not found"},
            409: {"description": f"A {label} with this name already exists"},
        },
        operation_id=f"rename_{label}",
    )
    def rename_item(
        item_id: int, data: NamedItemRequest, db: Session = Depends(get_db)
    ):
        item = db.get(model, item_id)
        if item is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"The {label} was not found.",
            )
        taken = db.scalar(
            select(model).where(model.name == data.name, model.id != item_id)
        )
        if taken is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A {label} with this name already exists.",
            )
        item.name = data.name
        db.commit()
        db.refresh(item)
        return item

    @router.delete(
        f"/{path}/{{item_id}}/",
        response_model=MessageResponse,
        summary=f"Delete a {label}",
        description=f"A {label} that is linked to movies cannot be deleted.",
        responses={
            **ACCESS_ERRORS,
            404: {"description": f"The {label} was not found"},
            409: {"description": f"The {label} is linked to movies"},
        },
        operation_id=f"delete_{label}",
    )
    def delete_item(item_id: int, db: Session = Depends(get_db)):
        item = db.get(model, item_id)
        if item is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"The {label} was not found.",
            )
        if item.movies:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"The {label} is linked to movies and cannot be deleted.",
            )
        db.delete(item)
        db.commit()
        return MessageResponse(message=f"The {label} was deleted.")


_register_named_crud(Genre, "genres", "genre")
_register_named_crud(Star, "stars", "star")
_register_named_crud(Director, "directors", "director")
