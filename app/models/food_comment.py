from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class FoodComment(Base):
    __tablename__ = "food_comments"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    food_id: Mapped[int] = mapped_column(ForeignKey("food.id", ondelete="RESTRICT"), nullable=False, index=True)
    parent_comment_id: Mapped[int | None] = mapped_column(
        ForeignKey("food_comments.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    content: Mapped[str] = mapped_column(Text(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user = relationship("User", back_populates="food_comments")
    food = relationship("Food", back_populates="comments")
    parent = relationship(
        "FoodComment",
        remote_side=[id],
        back_populates="replies",
        foreign_keys=[parent_comment_id],
    )
    replies = relationship(
        "FoodComment",
        back_populates="parent",
        foreign_keys=[parent_comment_id],
        cascade="all, delete",
    )
