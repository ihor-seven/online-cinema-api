import math
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.database import get_db
from src.dependencies import get_current_user
from src.models import (
    Comment,
    FavoriteMovie,
    Movie,
    MovieReaction,
    User,
    UserGroupEnum,
)
from src.schemas.accounts import MessageResponse
from src.schemas.interactions import (
    CommentCreateRequest,
    CommentListResponse,
    CommentSchema,
    ReactionCountsResponse,
    ReactionEnum,
    ReactionRequest,
)
from src.schemas.movies import MovieFilters, MovieListResponse
from src.services.movies import get_movies_page

router = APIRouter(prefix="/api/v1", tags=["Movie interactions"])

AUTH_401 = {401: {"description": "Missing, invalid or expired access token"}}
MOVIE_404 = {404: {"description": "Movie not found"}}


def _get_movie_or_404(db: Session, movie_id: int) -> Movie:
    movie = db.get(Movie, movie_id)
    if movie is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movie with the given ID was not found.",
        )
    return movie


# ---------- Favorites ----------


@router.post(
    "/movies/{movie_id}/favorite/",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a movie to favorites",
    description="Adds the movie to the favorites of the current user.",
    responses={
        **AUTH_401,
        **MOVIE_404,
        409: {"description": "The movie is already in favorites"},
    },
)
def add_to_favorites(
    movie_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_movie_or_404(db, movie_id)

    if db.get(FavoriteMovie, (current_user.id, movie_id)) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The movie is already in your favorites.",
        )

    db.add(FavoriteMovie(user_id=current_user.id, movie_id=movie_id))
    db.commit()
    return MessageResponse(message="Movie added to favorites.")


@router.delete(
    "/movies/{movie_id}/favorite/",
    response_model=MessageResponse,
    summary="Remove a movie from favorites",
    description="Removes the movie from the favorites of the current user.",
    responses={
        **AUTH_401,
        404: {"description": "The movie is not in favorites"},
    },
)
def remove_from_favorites(
    movie_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    favorite = db.get(FavoriteMovie, (current_user.id, movie_id))
    if favorite is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The movie is not in your favorites.",
        )

    db.delete(favorite)
    db.commit()
    return MessageResponse(message="Movie removed from favorites.")


@router.get(
    "/favorites/",
    response_model=MovieListResponse,
    summary="List favorite movies",
    description=(
        "Returns the favorite movies of the current user. Supports the same "
        "pagination, filters, search and sorting as `GET /movies/`."
    ),
    responses={**AUTH_401, 422: {"description": "Invalid query parameters"}},
)
def list_favorites(
    filters: Annotated[MovieFilters, Query()],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stmt = (
        select(Movie)
        .join(FavoriteMovie, FavoriteMovie.movie_id == Movie.id)
        .where(FavoriteMovie.user_id == current_user.id)
    )
    return get_movies_page(db, stmt, filters)


# ---------- Likes and dislikes ----------


@router.put(
    "/movies/{movie_id}/reaction/",
    response_model=ReactionCountsResponse,
    summary="Like or dislike a movie",
    description=(
        "Sets the reaction of the current user to `like` or `dislike`. "
        "A user has at most one reaction per movie: sending a different "
        "value changes it. Returns the updated counters."
    ),
    responses={**AUTH_401, **MOVIE_404, 422: {"description": "Invalid reaction"}},
)
def set_reaction(
    movie_id: int,
    data: ReactionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_movie_or_404(db, movie_id)

    is_like = data.reaction == ReactionEnum.LIKE
    reaction = db.get(MovieReaction, (current_user.id, movie_id))
    if reaction is None:
        db.add(MovieReaction(user_id=current_user.id, movie_id=movie_id, is_like=is_like))
    else:
        reaction.is_like = is_like
    db.commit()

    return _reaction_counts(db, movie_id)


@router.delete(
    "/movies/{movie_id}/reaction/",
    response_model=ReactionCountsResponse,
    summary="Remove your like or dislike",
    description="Removes the reaction of the current user. Returns the updated counters.",
    responses={
        **AUTH_401,
        404: {"description": "You have no reaction on this movie"},
    },
)
def remove_reaction(
    movie_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    reaction = db.get(MovieReaction, (current_user.id, movie_id))
    if reaction is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="You have no reaction on this movie.",
        )

    db.delete(reaction)
    db.commit()
    return _reaction_counts(db, movie_id)


@router.get(
    "/movies/{movie_id}/reactions/",
    response_model=ReactionCountsResponse,
    summary="Get the number of likes and dislikes",
    description="Public endpoint. Returns how many likes and dislikes the movie has.",
    responses=MOVIE_404,
)
def get_reactions(movie_id: int, db: Session = Depends(get_db)):
    _get_movie_or_404(db, movie_id)
    return _reaction_counts(db, movie_id)


def _reaction_counts(db: Session, movie_id: int) -> ReactionCountsResponse:
    def count(is_like: bool) -> int:
        return (
            db.scalar(
                select(func.count())
                .select_from(MovieReaction)
                .where(
                    MovieReaction.movie_id == movie_id,
                    MovieReaction.is_like.is_(is_like),
                )
            )
            or 0
        )

    return ReactionCountsResponse(likes=count(True), dislikes=count(False))


# ---------- Comments ----------


@router.post(
    "/movies/{movie_id}/comments/",
    response_model=CommentSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Write a comment",
    description="Adds a comment (1-1000 characters) to the movie.",
    responses={**AUTH_401, **MOVIE_404, 422: {"description": "Invalid comment text"}},
)
def create_comment(
    movie_id: int,
    data: CommentCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_movie_or_404(db, movie_id)

    comment = Comment(user_id=current_user.id, movie_id=movie_id, text=data.text)
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return comment


@router.get(
    "/movies/{movie_id}/comments/",
    response_model=CommentListResponse,
    summary="List comments of a movie",
    description="Public endpoint. Returns comments of the movie, newest first.",
    responses=MOVIE_404,
)
def list_comments(
    movie_id: int,
    page: int = Query(1, ge=1, description="Page number, starting from 1"),
    per_page: int = Query(10, ge=1, le=50, description="Items per page (max 50)"),
    db: Session = Depends(get_db),
):
    _get_movie_or_404(db, movie_id)

    total_items = (
        db.scalar(
            select(func.count()).select_from(Comment).where(Comment.movie_id == movie_id)
        )
        or 0
    )
    items = db.scalars(
        select(Comment)
        .where(Comment.movie_id == movie_id)
        .order_by(Comment.created_at.desc(), Comment.id.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    ).all()

    return {
        "items": items,
        "page": page,
        "per_page": per_page,
        "total_items": total_items,
        "total_pages": math.ceil(total_items / per_page),
    }


@router.delete(
    "/comments/{comment_id}/",
    response_model=MessageResponse,
    summary="Delete a comment",
    description=(
        "The author can delete their own comment. "
        "Moderators and admins can delete any comment."
    ),
    responses={
        **AUTH_401,
        403: {"description": "You cannot delete someone else's comment"},
        404: {"description": "Comment not found"},
    },
)
def delete_comment(
    comment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    comment = db.get(Comment, comment_id)
    if comment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found."
        )

    is_author = comment.user_id == current_user.id
    is_staff = current_user.group.name in (
        UserGroupEnum.MODERATOR,
        UserGroupEnum.ADMIN,
    )
    if not (is_author or is_staff):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can delete only your own comments.",
        )

    db.delete(comment)
    db.commit()
    return MessageResponse(message="Comment deleted.")