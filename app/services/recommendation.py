from datetime import date, timedelta

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.enums import ReviewSentiment
from app.models.food_record import FoodRecord
from app.models.reaction import FoodReaction
from app.models.user import User


def get_daily_recommendation(db: Session, current_user: User | None = None) -> FoodRecord | None:
    yesterday = date.today() - timedelta(days=1)
    query = (
        db.query(FoodRecord)
        .filter(FoodRecord.is_public.is_(True), FoodRecord.visited_at >= yesterday)
        .outerjoin(FoodReaction, FoodReaction.food_record_id == FoodRecord.id)
        .group_by(FoodRecord.id)
        .order_by(func.count(FoodReaction.id).desc(), FoodRecord.created_at.desc())
    )
    record = query.first()
    if record:
        return record

    if current_user:
        return (
            db.query(FoodRecord)
            .filter(FoodRecord.user_id == current_user.id)
            .order_by(FoodRecord.created_at.desc())
            .first()
        )

    return db.query(FoodRecord).order_by(FoodRecord.created_at.desc()).first()


def get_personalized_recommendations(db: Session, current_user: User, limit: int = 5) -> list[FoodRecord]:
    liked_tags = (
        db.query(FoodRecord.tags)
        .filter(
            FoodRecord.user_id == current_user.id,
            FoodRecord.sentiment == ReviewSentiment.like,
        )
        .all()
    )
    keywords = {
        tag.strip()
        for (tags,) in liked_tags
        if tags
        for tag in tags.split(',')
        if tag.strip()
    }

    query = db.query(FoodRecord).filter(
        FoodRecord.user_id != current_user.id,
        FoodRecord.is_public.is_(True),
    )

    if keywords:
        query = query.filter(or_(*[FoodRecord.tags.contains(keyword) for keyword in keywords]))

    return query.order_by(FoodRecord.created_at.desc()).limit(limit).all()
