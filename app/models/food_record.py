from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import DiningCategory, RatingLevel, ReviewSentiment


class FoodRecord(Base):
    __tablename__ = "food_records"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    food_name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    dining_category: Mapped[DiningCategory] = mapped_column(Enum(DiningCategory), nullable=False)
    canteen_name: Mapped[str | None] = mapped_column(String(120))
    floor: Mapped[str | None] = mapped_column(String(50))
    window_name: Mapped[str | None] = mapped_column(String(120))
    store_name: Mapped[str | None] = mapped_column(String(120))
    address: Mapped[str | None] = mapped_column(String(255))
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    sentiment: Mapped[ReviewSentiment] = mapped_column(Enum(ReviewSentiment), nullable=False)
    rating_level: Mapped[RatingLevel] = mapped_column(Enum(RatingLevel), nullable=False)
    review_text: Mapped[str | None] = mapped_column(Text())
    image_url: Mapped[str | None] = mapped_column(String(255))
    tags: Mapped[str | None] = mapped_column(String(255))
    visited_at: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    is_public: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    user = relationship("User", back_populates="food_records")
    reactions = relationship("FoodReaction", back_populates="food_record", cascade="all, delete-orphan")
    comments = relationship("Comment", back_populates="food_record", cascade="all, delete-orphan")
