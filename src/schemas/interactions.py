import enum
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints


class ReactionEnum(str, enum.Enum):
    LIKE = "like"
    DISLIKE = "dislike"


class ReactionRequest(BaseModel):
    reaction: ReactionEnum


class ReactionCountsResponse(BaseModel):
    likes: int
    dislikes: int


class CommentCreateRequest(BaseModel):
    text: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)
    ]


class CommentSchema(BaseModel):
    id: int
    movie_id: int
    user_id: int
    text: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CommentListResponse(BaseModel):
    items: list[CommentSchema]
    page: int
    per_page: int
    total_items: int
    total_pages: int
    