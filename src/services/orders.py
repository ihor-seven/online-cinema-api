import math
from decimal import Decimal

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, selectinload

from src.models import (
    Cart,
    CartItem,
    Order,
    OrderItem,
    OrderStatusEnum,
)


class OrderError(Exception):
    def __init__(self, message: str, excluded: list[dict] | None = None):
        super().__init__(message)
        self.message = message
        self.excluded = excluded or []


def get_movie_ids_by_status(
    db: Session, user_id: int, status: OrderStatusEnum
) -> set[int]:
    stmt = (
        select(OrderItem.movie_id)
        .join(Order, Order.id == OrderItem.order_id)
        .where(Order.user_id == user_id, Order.status == status)
    )
    return set(db.scalars(stmt).all())


def create_order_from_cart(db: Session, user_id: int) -> tuple[Order, list[dict]]:
    cart_items = db.scalars(
        select(CartItem)
        .join(Cart, Cart.id == CartItem.cart_id)
        .where(Cart.user_id == user_id)
        .options(selectinload(CartItem.movie))
        .order_by(CartItem.added_at, CartItem.id)
    ).all()

    if not cart_items:
        raise OrderError("Your cart is empty.")

    purchased = get_movie_ids_by_status(db, user_id, OrderStatusEnum.PAID)
    pending = get_movie_ids_by_status(db, user_id, OrderStatusEnum.PENDING)

    order = Order(user_id=user_id, status=OrderStatusEnum.PENDING)
    excluded: list[dict] = []

    for cart_item in cart_items:
        movie = cart_item.movie
        if movie.id in purchased:
            excluded.append(
                {"movie_id": movie.id, "name": movie.name, "reason": "already_purchased"}
            )
        elif movie.id in pending:
            excluded.append(
                {"movie_id": movie.id, "name": movie.name, "reason": "pending_order"}
            )
        else:
            order.items.append(
                OrderItem(movie_id=movie.id, price_at_order=movie.price)
            )

    if not order.items:
        raise OrderError("None of the movies in your cart can be ordered.", excluded)

    order.total_amount = sum(
        (item.price_at_order for item in order.items), Decimal("0.00")
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order, excluded


def get_orders_page(db: Session, stmt: Select, page: int, per_page: int) -> dict:
    total_items = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    stmt = (
        stmt.order_by(Order.created_at.desc(), Order.id.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .options(selectinload(Order.items).selectinload(OrderItem.movie))
    )
    return {
        "items": db.scalars(stmt).all(),
        "page": page,
        "per_page": per_page,
        "total_items": total_items,
        "total_pages": math.ceil(total_items / per_page),
    }
