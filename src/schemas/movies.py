import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class NamedItemSchema(BaseModel):
    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)


class MovieListItemSchema(BaseModel):
    id: int
    uuid: uuid.UUID
    name: str
    year: int
    time: int
    imdb: float
    votes: int
    price: Decimal
    genres: list[NamedItemSchema]

    model_config = ConfigDict(from_attributes=True)


class MovieDetailSchema(MovieListItemSchema):
    meta_score: float | None
    gross: float | None
    description: str
    certification: NamedItemSchema
    stars: list[NamedItemSchema]
    directors: list[NamedItemSchema]


class MovieListResponse(BaseModel):
    items: list[MovieListItemSchema]
    page: int
    per_page: int
    total_items: int
    total_pages: int


class GenreWithCountSchema(BaseModel):
    id: int
    name: str
    movie_count: int
    