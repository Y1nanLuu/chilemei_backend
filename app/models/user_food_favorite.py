from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class UserFoodFavorite(Base):
    __tablename__ = "user_food_favorites"
    __table_args__ = (UniqueConstraint("user_id", "food_id", name="uk_user_food_favorites_user_food"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    food_id: Mapped[int] = mapped_column(ForeignKey("food.id", ondelete="RESTRICT"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user = relationship("User", back_populates="food_favorites")
    food = relationship("Food", back_populates="user_favorites")
