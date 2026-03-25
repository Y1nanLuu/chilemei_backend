from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import DiningCategory, RatingLevel, ReviewSentiment


class FoodRecordBase(BaseModel):
    food_name: str = Field(min_length=1, max_length=120)
    dining_category: DiningCategory
    canteen_name: str | None = Field(default=None, max_length=120)
    floor: str | None = Field(default=None, max_length=50)
    window_name: str | None = Field(default=None, max_length=120)
    store_name: str | None = Field(default=None, max_length=120)
    address: str | None = Field(default=None, max_length=255)
    price: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    sentiment: ReviewSentiment
    rating_level: RatingLevel
    review_text: str | None = None
    image_url: str | None = Field(default=None, max_length=255)
    tags: list[str] = Field(default_factory=list)
    visited_at: date
    is_public: bool = True


class FoodRecordCreate(FoodRecordBase):
    pass


class FoodRecordUpdate(BaseModel):
    food_name: str | None = Field(default=None, min_length=1, max_length=120)
    dining_category: DiningCategory | None = None
    canteen_name: str | None = Field(default=None, max_length=120)
    floor: str | None = Field(default=None, max_length=50)
    window_name: str | None = Field(default=None, max_length=120)
    store_name: str | None = Field(default=None, max_length=120)
    address: str | None = Field(default=None, max_length=255)
    price: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    sentiment: ReviewSentiment | None = None
    rating_level: RatingLevel | None = None
    review_text: str | None = None
    image_url: str | None = Field(default=None, max_length=255)
    tags: list[str] | None = None
    visited_at: date | None = None
    is_public: bool | None = None


class FoodRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    food_name: str
    dining_category: DiningCategory
    canteen_name: str | None
    floor: str | None
    window_name: str | None
    store_name: str | None
    address: str | None
    price: Decimal
    sentiment: ReviewSentiment
    rating_level: RatingLevel
    review_text: str | None
    image_url: str | None
    tags: list[str]
    visited_at: date
    is_public: bool
    like_count: int = 0
    dislike_count: int = 0
    want_to_eat_count: int = 0
    created_at: datetime


class FoodRankingItem(BaseModel):
    food_record_id: int
    food_name: str
    dining_location: str
    price: Decimal
    like_count: int
    dislike_count: int
    want_to_eat_count: int
    score: int
