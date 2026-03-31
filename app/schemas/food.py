from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ReviewSentiment

RatingLevelValue = Annotated[int, Field(ge=1, le=5)]


class FoodBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    location: str = Field(min_length=1, max_length=255)
    price: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    image_url: str | None = Field(default=None, max_length=255)


class FoodCreate(FoodBase):
    pass


class FoodUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    location: str | None = Field(default=None, min_length=1, max_length=255)
    price: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    image_url: str | None = Field(default=None, max_length=255)


class FoodResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    location: str
    price: Decimal
    image_url: str | None


class FoodRecordCreate(BaseModel):
    food: FoodCreate
    sentiment: ReviewSentiment
    rating_level: RatingLevelValue
    review_text: str | None = None
    image_url: str | None = Field(default=None, max_length=255)
    uploaded_at: datetime | None = None


class FoodRecordUpdate(BaseModel):
    food: FoodUpdate | None = None
    sentiment: ReviewSentiment | None = None
    rating_level: RatingLevelValue | None = None
    review_text: str | None = None
    image_url: str | None = Field(default=None, max_length=255)
    uploaded_at: datetime | None = None


class FoodRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    food_id: int
    food: FoodResponse
    sentiment: ReviewSentiment
    rating_level: RatingLevelValue
    review_text: str | None
    image_url: str | None
    uploaded_at: datetime
    like_count: int = 0
    dislike_count: int = 0
    created_at: datetime
    updated_at: datetime


class FoodRankingItem(BaseModel):
    food_id: int
    food_name: str
    location: str
    price: Decimal
    like_count: int
    dislike_count: int
    score: float


class UserFoodStatsResponse(BaseModel):
    user_id: int
    food_id: int
    like_count: int
    dislike_count: int


class FoodImageUploadResponse(BaseModel):
    image_url: str
    stored_path: str
    original_filename: str
