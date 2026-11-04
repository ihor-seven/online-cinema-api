from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from src.database import get_db
from src.dependencies import get_current_user
from src.models import Cart, CartItem, Movie, User
from src.schemas.cart import CartAddRequest, CartResponse
from src.services.cart import get_cart_view, get_or_create_cart

router = APIRouter(prefix="/api/v1/cart", tags=["Cart"])

AUTH_401 = {401: {"description": "Missing, invalid or expired access token"}}


@router.get(
    "/",
    response_model=CartResponse,
    summary="View the cart",
    description=(
        "Returns the movies in the cart of the current user: title, price, "
        "genres and release year, plus the number of items and the total price."
    ),
    responses=AUTH_401,
)
def view_cart(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    return get_cart_view(db, current_user.id)


@router.post(
    "/items/",
    response_model=CartResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a movie to the cart",
    description="Adds a movie to the cart and returns the updated cart.",
    responses={
        **AUTH_401,
        404: {"description": "Movie not found"},
        409: {"description": "The movie is already in the cart"},
    },
)
def add_to_cart(
    data: CartAddRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    movie = db.get(Movie, data.movie_id)
    if movie is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movie with the given ID was not found.",
        )

    cart = get_or_create_cart(db, current_user.id)
    already_in_cart = db.scalar(
        select(CartItem).where(
            CartItem.cart_id == cart.id, CartItem.movie_id == movie.id
        )
    )
    if already_in_cart is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The movie is already in your cart.",
        )

    db.add(CartItem(cart_id=cart.id, movie_id=movie.id))
    db.commit()
    return get_cart_view(db, current_user.id)


@router.delete(
    "/items/{movie_id}/",
    response_model=CartResponse,
    summary="Remove a movie from the cart",
    description="Removes one movie from the cart and returns the updated cart.",
    responses={**AUTH_401, 404: {"description": "The movie is not in the cart"}},
)
def remove_from_cart(
    movie_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = db.scalar(
        select(CartItem)
        .join(Cart, Cart.id == CartItem.cart_id)
        .where(Cart.user_id == current_user.id, CartItem.movie_id == movie_id)
    )
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The movie is not in your cart.",
        )

    db.delete(item)
    db.commit()
    return get_cart_view(db, current_user.id)


@router.delete(
    "/",
    response_model=CartResponse,
    summary="Clear the cart",
    description="Removes all movies from the cart. Returns the empty cart.",
    responses=AUTH_401,
)
def clear_cart(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    cart = db.scalar(select(Cart).where(Cart.user_id == current_user.id))
    if cart is not None:
        db.execute(delete(CartItem).where(CartItem.cart_id == cart.id))
        db.commit()
    return get_cart_view(db, current_user.id)
