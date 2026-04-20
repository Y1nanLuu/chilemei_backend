from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ReviewSentiment


class ReactionCreate(BaseModel):
    reaction_type: ReviewSentiment


class CommentCreate(BaseModel):
    content: str = Field(min_length=1, max_length=1000)


class FoodCommentCreate(BaseModel):
    content: str = Field(min_length=1, max_length=1000)
    parent_comment_id: int | None = Field(default=None, gt=0)


class CommentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    food_record_id: int
    content: str
    created_at: datetime


class FoodCommentResponse(BaseModel):
    id: int
    user_id: int
    user_nickname: str
    user_avatar_url: str | None = None
    avatar_url: str | None = None
    food_id: int
    parent_comment_id: int | None = None
    parent_user_id: int | None = None
    parent_user_nickname: str | None = None
    parent_user_avatar_url: str | None = None
    content: str
    created_at: datetime
