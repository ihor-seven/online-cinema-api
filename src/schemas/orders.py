from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from src.models import OrderStatusEnum


class OrderItemSchema(BaseModel):
    movie_id: int
    movie_name: str
    price_at_order: Decimal

    model_config = ConfigDict(from_attributes=True)


class OrderSchema(BaseModel):
    id: int
    created_at: datetime
    status: OrderStatusEnum
    total_amount: Decimal | None
    items: list[OrderItemSchema]

    model_config = ConfigDict(from_attributes=True)


class ExcludedMovieSchema(BaseModel):
    movie_id: int
    name: str
    reason: str


class OrderCreateResponse(BaseModel):
    order: OrderSchema
    excluded: list[ExcludedMovieSchema]


class OrderListResponse(BaseModel):
    items: list[OrderSchema]
    page: int
    per_page: int
    total_items: int
    total_pages: int
    