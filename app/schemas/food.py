from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import RatingLevel, ReviewSentiment


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
    rating_level: RatingLevel
    review_text: str | None = None
    image_url: str | None = Field(default=None, max_length=255)
    uploaded_at: datetime | None = None


class FoodRecordUpdate(BaseModel):
    food: FoodUpdate | None = None
    sentiment: ReviewSentiment | None = None
    rating_level: RatingLevel | None = None
    review_text: str | None = None
    image_url: str | None = Field(default=None, max_length=255)
    uploaded_at: datetime | None = None


class FoodRecordResponse(BaseModel):
    id: int
    user_id: int
    food_id: int
    food: FoodResponse
    sentiment: ReviewSentiment
    rating_level: RatingLevel
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
    score: int


class UserFoodStatsResponse(BaseModel):
    user_id: int
    food_id: int
    like_count: int
    dislike_count: int
