import enum
import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class MovieSortBy(str, enum.Enum):
    PRICE = "price"
    YEAR = "year"
    IMDB = "imdb"
    VOTES = "votes"
    NAME = "name"


class SortOrder(str, enum.Enum):
    ASC = "asc"
    DESC = "desc"


class MovieFilters(BaseModel):
    page: int = Field(1, ge=1, description="Page number, starting from 1")
    per_page: int = Field(10, ge=1, le=20, description="Items per page (max 20)")
    year: int | None = Field(None, description="Exact release year")
    min_year: int | None = Field(None, description="Released in or after this year")
    max_year: int | None = Field(None, description="Released in or before this year")
    min_imdb: float | None = Field(None, ge=0, le=10, description="Minimum IMDb rating")
    max_imdb: float | None = Field(None, ge=0, le=10, description="Maximum IMDb rating")
    genre_id: int | None = Field(None, description="Only movies of this genre")
    search: str | None = Field(
        None,
        min_length=1,
        description="Text to search in title, description, stars and directors",
    )
    sort_by: MovieSortBy = Field(MovieSortBy.YEAR, description="Field to sort by")
    order: SortOrder = Field(SortOrder.DESC, description="Sort direction")


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
    