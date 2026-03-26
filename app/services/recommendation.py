from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.enums import ReviewSentiment
from app.models.food import Food
from app.models.food_record import FoodRecord
from app.models.user import User


def get_daily_recommendation(db: Session, current_user: User | None = None) -> FoodRecord | None:
    threshold = datetime.now(timezone.utc) - timedelta(days=1)
    query = db.query(FoodRecord).join(Food).join(User, User.id == FoodRecord.user_id)

    if current_user:
        query = query.filter((FoodRecord.user_id == current_user.id) | (User.is_private.is_(False)))
    else:
        query = query.filter(User.is_private.is_(False))

    record = query.filter(FoodRecord.uploaded_at >= threshold).order_by(FoodRecord.uploaded_at.desc()).first()
    if record:
        return record

    return query.order_by(FoodRecord.uploaded_at.desc()).first()


def get_personalized_recommendations(db: Session, current_user: User, limit: int = 5) -> list[FoodRecord]:
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
        db.query(FoodRecord)
        .join(Food)
        .join(User, User.id == FoodRecord.user_id)
        .filter(FoodRecord.user_id != current_user.id, User.is_private.is_(False))
    )

    if preferred_locations:
        query = query.filter(Food.location.in_(preferred_locations[:3]))
    if seen_food_ids:
        query = query.filter(~FoodRecord.food_id.in_(seen_food_ids))

    return query.order_by(FoodRecord.uploaded_at.desc()).limit(limit).all()
