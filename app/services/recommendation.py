from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.enums import ReviewSentiment
from app.models.food import Food
from app.models.food_record import FoodRecord
from app.models.user import User


def get_daily_recommendation(db: Session, current_user: User | None = None) -> Food | None:
    threshold = datetime.now(timezone.utc) - timedelta(days=1)
    query = db.query(Food).join(FoodRecord).join(User, User.id == FoodRecord.user_id)

    if current_user:
        query = query.filter((FoodRecord.user_id == current_user.id) | (User.is_private.is_(False)))
    else:
        query = query.filter(User.is_private.is_(False))

    recent_food = (
        query.filter(FoodRecord.uploaded_at >= threshold)
        .group_by(Food.id)
        .order_by(func.max(FoodRecord.uploaded_at).desc(), Food.id.desc())
        .first()
    )
    if recent_food:
        return recent_food

    return query.group_by(Food.id).order_by(func.max(FoodRecord.uploaded_at).desc(), Food.id.desc()).first()


def get_personalized_recommendations(db: Session, current_user: User, limit: int = 5) -> list[Food]:
    liked_records = (
        db.query(FoodRecord)
        .join(Food)
        .filter(FoodRecord.user_id == current_user.id, FoodRecord.sentiment == ReviewSentiment.like)
        .order_by(FoodRecord.uploaded_at.desc())
        .all()
    )
    preferred_locations = []
    seen_food_ids = set()
    for record in liked_records:
        seen_food_ids.add(record.food_id)
        location = record.food.location
        if location not in preferred_locations:
            preferred_locations.append(location)

    query = (
        db.query(Food)
        .join(FoodRecord)
        .join(User, User.id == FoodRecord.user_id)
        .filter(FoodRecord.user_id != current_user.id, User.is_private.is_(False))
    )

    if preferred_locations:
        query = query.filter(Food.location.in_(preferred_locations[:3]))
    if seen_food_ids:
        query = query.filter(~Food.id.in_(seen_food_ids))

    return (
        query.group_by(Food.id)
        .order_by(func.max(FoodRecord.uploaded_at).desc(), Food.id.desc())
        .limit(limit)
        .all()
    )