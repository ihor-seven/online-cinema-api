from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from src.schemas.movies import NamedItemSchema


class CartAddRequest(BaseModel):
    movie_id: int


class CartItemSchema(BaseModel):
    movie_id: int
    name: str
    year: int
    price: Decimal
    genres: list[NamedItemSchema]
    added_at: datetime


class CartResponse(BaseModel):
    items: list[CartItemSchema]
    total_items: int
    total_price: Decimal
    