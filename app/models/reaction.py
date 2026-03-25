from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import ReactionType


class FoodReaction(Base):
    __tablename__ = "food_reactions"
    __table_args__ = (UniqueConstraint("user_id", "food_record_id", "reaction_type"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    food_record_id: Mapped[int] = mapped_column(
        ForeignKey("food_records.id"), nullable=False, index=True
    )
    reaction_type: Mapped[ReactionType] = mapped_column(Enum(ReactionType), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user = relationship("User", back_populates="reactions")
    food_record = relationship("FoodRecord", back_populates="reactions")
