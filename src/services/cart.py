from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from src.models import Cart, CartItem, Movie


def get_or_create_cart(db: Session, user_id: int) -> Cart:
    cart = db.scalar(select(Cart).where(Cart.user_id == user_id))
    if cart is None:
        cart = Cart(user_id=user_id)
        db.add(cart)
        db.flush()
    return cart


def get_cart_view(db: Session, user_id: int) -> dict:
    stmt = (
        select(CartItem)
        .join(Cart, Cart.id == CartItem.cart_id)
        .where(Cart.user_id == user_id)
        .options(selectinload(CartItem.movie).selectinload(Movie.genres))
        .order_by(CartItem.added_at, CartItem.id)
    )
    items = db.scalars(stmt).all()

    return {
        "items": [
            {
                "movie_id": item.movie_id,
                "name": item.movie.name,
                "year": item.movie.year,
                "price": item.movie.price,
                "genres": item.movie.genres,
                "added_at": item.added_at,
            }
            for item in items
        ],
        "total_items": len(items),
        "total_price": sum((item.movie.price for item in items), Decimal("0.00")),
    }
