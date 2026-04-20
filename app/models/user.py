from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    wechat_openid: Mapped[str | None] = mapped_column(String(100), unique=True, index=True)
    wechat_unionid: Mapped[str | None] = mapped_column(String(100), unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(50), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(120), unique=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    nickname: Mapped[str] = mapped_column(String(50), nullable=False)
    bio: Mapped[str | None] = mapped_column(String(255))
    avatar_url: Mapped[str | None] = mapped_column(String(255))
    gender: Mapped[str | None] = mapped_column(String(20))
    grade: Mapped[str | None] = mapped_column(String(20))
    campus: Mapped[str | None] = mapped_column(String(20))
    is_private: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    taste_preferences: Mapped[list[str] | None] = mapped_column(JSON)
    taboo_list: Mapped[list[str] | None] = mapped_column(JSON)
    spicy_level: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    food_records = relationship("FoodRecord", back_populates="user")
    food_stats = relationship("UserFoodStat", back_populates="user")
    food_favorites = relationship("UserFoodFavorite", back_populates="user")
    comments = relationship("Comment", back_populates="user")
