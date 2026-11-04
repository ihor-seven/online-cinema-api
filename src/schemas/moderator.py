from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints, model_validator

Name = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
]

NULLABLE_FIELDS = {"meta_score", "gross"}


class NamedItemRequest(BaseModel):
    name: Name


class MovieCreateRequest(BaseModel):
    name: Name
    year: int = Field(ge=1888, le=2100)
    time: int = Field(ge=1, le=1000, description="Duration in minutes")
    imdb: float = Field(ge=0, le=10)
    votes: int = Field(ge=0)
    meta_score: float | None = Field(None, ge=0, le=100)
    gross: float | None = Field(None, ge=0)
    description: str = Field(min_length=1)
    price: Decimal = Field(ge=0, max_digits=10, decimal_places=2)
    certification: Name
    genres: list[Name] = Field(default_factory=list)
    stars: list[Name] = Field(default_factory=list)
    directors: list[Name] = Field(default_factory=list)


class MovieUpdateRequest(BaseModel):
    name: Name | None = None
    year: int | None = Field(None, ge=1888, le=2100)
    time: int | None = Field(None, ge=1, le=1000)
    imdb: float | None = Field(None, ge=0, le=10)
    votes: int | None = Field(None, ge=0)
    meta_score: float | None = Field(None, ge=0, le=100)
    gross: float | None = Field(None, ge=0)
    description: str | None = Field(None, min_length=1)
    price: Decimal | None = Field(None, ge=0, max_digits=10, decimal_places=2)
    certification: Name | None = None
    genres: list[Name] | None = None
    stars: list[Name] | None = None
    directors: list[Name] | None = None

    @model_validator(mode="after")
    def check_sent_fields(self):
        if not self.model_fields_set:
            raise ValueError("Send at least one field to update")
        for field in self.model_fields_set:
            if field not in NULLABLE_FIELDS and getattr(self, field) is None:
                raise ValueError(f"Field '{field}' cannot be null")
        return self
    