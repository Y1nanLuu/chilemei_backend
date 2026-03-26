from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ReviewSentiment


class ReactionCreate(BaseModel):
    reaction_type: ReviewSentiment


class CommentCreate(BaseModel):
    content: str = Field(min_length=1, max_length=1000)


class CommentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    food_record_id: int
    content: str
    created_at: datetime
