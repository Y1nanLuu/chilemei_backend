from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import RatingLevel, ReviewSentiment


class FoodRecord(Base):
    __tablename__ = "food_records"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    food_id: Mapped[int] = mapped_column(ForeignKey("food.id", ondelete="RESTRICT"), nullable=False, index=True)
    sentiment: Mapped[ReviewSentiment] = mapped_column(Enum(ReviewSentiment), nullable=False)
    rating_level: Mapped[RatingLevel] = mapped_column(Enum(RatingLevel), nullable=False)
    review_text: Mapped[str | None] = mapped_column(Text())
    image_url: Mapped[str | None] = mapped_column(String(255))
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    user = relationship("User", back_populates="food_records")
    food = relationship("Food", back_populates="records")
    comments = relationship("Comment", back_populates="food_record", cascade="all, delete-orphan")
