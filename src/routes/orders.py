from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from src.database import get_db
from src.dependencies import get_current_user
from src.models import Movie, Order, OrderItem, OrderStatusEnum, User
from src.schemas.movies import MovieFilters, MovieListResponse
from src.schemas.orders import OrderCreateResponse, OrderListResponse, OrderSchema
from src.services.movies import get_movies_page
from src.services.orders import OrderError, create_order_from_cart, get_orders_page

router = APIRouter(prefix="/api/v1", tags=["Orders"])

AUTH_401 = {401: {"description": "Missing, invalid or expired access token"}}


@router.post(
    "/orders/",
    response_model=OrderCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an order from the cart",
    description=(
        "Creates a `pending` order from the movies in the cart. Movies that "
        "were already purchased, or that are in another pending order, are "
        "not included: they are listed in `excluded` with a `reason` "
        "(`already_purchased` or `pending_order`). The price of every movie "
        "is saved at the moment of ordering."
    ),
    responses={
        **AUTH_401,
        400: {
            "description": "The cart is empty, or none of its movies can be ordered"
        },
    },
)
def create_order(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    try:
        order, excluded = create_order_from_cart(db, current_user.id)
    except OrderError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": exc.message, "excluded": exc.excluded},
        )
    return {"order": order, "excluded": excluded}


@router.get(
    "/orders/",
    response_model=OrderListResponse,
    summary="List my orders",
    description=(
        "Returns the orders of the current user, newest first: date and time, "
        "movies, total amount and status (`pending`, `paid`, `canceled`). "
        "Can be filtered by `status`."
    ),
    responses={**AUTH_401, 422: {"description": "Invalid query parameters"}},
)
def list_orders(
    page: int = Query(1, ge=1, description="Page number, starting from 1"),
    per_page: int = Query(10, ge=1, le=50, description="Items per page (max 50)"),
    order_status: OrderStatusEnum | None = Query(
        None, alias="status", description="Only orders with this status"
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stmt = select(Order).where(Order.user_id == current_user.id)
    if order_status is not None:
        stmt = stmt.where(Order.status == order_status)
    return get_orders_page(db, stmt, page, per_page)


@router.get(
    "/orders/{order_id}/",
    response_model=OrderSchema,
    summary="Get one of my orders",
    description="Returns an order of the current user with all its movies.",
    responses={**AUTH_401, 404: {"description": "Order not found"}},
)
def get_order(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _get_own_order_or_404(db, order_id, current_user.id)


@router.post(
    "/orders/{order_id}/cancel/",
    response_model=OrderSchema,
    summary="Cancel an order",
    description=(
        "Cancels a `pending` order. A paid order cannot be canceled this way: "
        "it can only be returned through a refund request."
    ),
    responses={
        **AUTH_401,
        400: {"description": "The order is paid or already canceled"},
        404: {"description": "Order not found"},
    },
)
def cancel_order(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    order = _get_own_order_or_404(db, order_id, current_user.id)

    if order.status == OrderStatusEnum.PAID:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A paid order can only be canceled via a refund request.",
        )
    if order.status == OrderStatusEnum.CANCELED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The order is already canceled.",
        )

    order.status = OrderStatusEnum.CANCELED
    db.commit()
    db.refresh(order)
    return order


@router.get(
    "/purchased/",
    response_model=MovieListResponse,
    summary="List purchased movies",
    description=(
        "Returns movies from the paid orders of the current user. Supports "
        "the same pagination, filters, search and sorting as `GET /movies/`."
    ),
    responses={**AUTH_401, 422: {"description": "Invalid query parameters"}},
)
def list_purchased_movies(
    filters: Annotated[MovieFilters, Query()],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    purchased_ids = (
        select(OrderItem.movie_id)
        .join(Order, Order.id == OrderItem.order_id)
        .where(
            Order.user_id == current_user.id,
            Order.status == OrderStatusEnum.PAID,
        )
    )
    return get_movies_page(db, select(Movie).where(Movie.id.in_(purchased_ids)), filters)


def _get_own_order_or_404(db: Session, order_id: int, user_id: int) -> Order:
    order = db.scalar(
        select(Order)
        .where(Order.id == order_id, Order.user_id == user_id)
        .options(selectinload(Order.items).selectinload(OrderItem.movie))
    )
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Order not found."
        )
    return order
