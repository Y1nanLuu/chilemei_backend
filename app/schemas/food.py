from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import ReviewSentiment

RatingLevelValue = Annotated[int, Field(ge=1, le=5)]


class FoodBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    location: str = Field(min_length=1, max_length=255)
    price: Decimal = Field(gt=0, max_digits=10, decimal_places=2)


class FoodCreate(FoodBase):
    pass


class FoodUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    location: str | None = Field(default=None, min_length=1, max_length=255)
    price: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)


class FoodResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    location: str
    price: Decimal
    image_dir: str | None


class FoodRecordCreate(BaseModel):
    food_id: int | None = Field(default=None, gt=0)
    food: FoodCreate | None = None
    sentiment: ReviewSentiment
    rating_level: RatingLevelValue
    review_text: str | None = None
    image_filename: str | None = Field(default=None, max_length=255)
    uploaded_at: datetime | None = None

    @model_validator(mode='after')
    def validate_food_selection(self) -> 'FoodRecordCreate':
        if (self.food_id is None) == (self.food is None):
            raise ValueError('Provide exactly one of food_id or food')
        return self


class FoodRecordUpdate(BaseModel):
    food_id: int | None = Field(default=None, gt=0)
    food: FoodUpdate | None = None
    sentiment: ReviewSentiment | None = None
    rating_level: RatingLevelValue | None = None
    review_text: str | None = None
    image_filename: str | None = Field(default=None, max_length=255)
    uploaded_at: datetime | None = None

    @model_validator(mode='after')
    def validate_food_selection(self) -> 'FoodRecordUpdate':
        if self.food_id is not None and self.food is not None:
            raise ValueError('Provide only one of food_id or food')
        return self


class FoodRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    food_id: int
    food: FoodResponse
    sentiment: ReviewSentiment
    rating_level: RatingLevelValue
    review_text: str | None
    image_filename: str | None
    image_url: str | None
    uploaded_at: datetime
    like_count: int = 0
    dislike_count: int = 0
    created_at: datetime
    updated_at: datetime


class FoodRecordReuseDraftResponse(BaseModel):
    source_record_id: int
    food_id: int
    food: FoodResponse
    sentiment: ReviewSentiment
    rating_level: RatingLevelValue
    review_text: str | None
    image_filename: str | None
    image_url: str | None


class FoodRecommendationItem(BaseModel):
    food_id: int
    name: str
    location: str
    price: Decimal
    score: float
    like_count: int
    dislike_count: int
    cover_image_url: str | None


class FoodDetailCommentResponse(BaseModel):
    id: int
    user_id: int
    user_nickname: str
    food_record_id: int
    content: str
    created_at: datetime


class FoodDetailResponse(BaseModel):
    food_id: int
    name: str
    location: str
    price: Decimal
    score: float
    like_count: int
    dislike_count: int
    cover_image_url: str | None
    image_urls: list[str]
    description: str | None
    comments: list[FoodDetailCommentResponse]


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
