from datetime import datetime, timedelta, timezone
from typing import Iterable

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.enums import ReviewSentiment
from app.models.food import Food
from app.models.food_record import FoodRecord
from app.models.user import User

SPICY_KEYWORDS: dict[int, tuple[str, ...]] = {
    0: ('不辣', '清淡'),
    1: ('微辣',),
    2: ('小辣',),
    3: ('中辣', '酸辣'),
    4: ('麻辣', '香辣', '川菜', '火锅'),
    5: ('爆辣', '特辣', '无辣不欢'),
}
GENERIC_SPICY_TERMS = ('辣', '麻辣', '香辣', '酸辣', '川菜', '火锅')


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


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


def _normalize_tags(tags: Iterable[str] | None) -> list[str]:
    if not tags:
        return []

    result: list[str] = []
    seen: set[str] = set()
    for item in tags:
        tag = str(item).strip()
        if not tag or tag in seen:
            continue
        seen.add(tag)
        result.append(tag)
    return result


def _food_corpus(db: Session, food: Food) -> str:
    review_rows = (
        db.query(FoodRecord.review_text)
        .join(User, User.id == FoodRecord.user_id)
        .filter(
            FoodRecord.food_id == food.id,
            User.is_private.is_(False),
            FoodRecord.review_text.isnot(None),
            FoodRecord.review_text != '',
        )
        .order_by(FoodRecord.uploaded_at.desc(), FoodRecord.id.desc())
        .limit(20)
        .all()
    )
    review_text = ' '.join((row[0] or '').strip() for row in review_rows if row[0])
    return f'{food.name} {food.location} {review_text}'.lower()


def _infer_spicy_strength(corpus: str) -> int:
    for level in range(5, -1, -1):
        if any(keyword.lower() in corpus for keyword in SPICY_KEYWORDS[level]):
            return level
    if any(keyword.lower() in corpus for keyword in GENERIC_SPICY_TERMS):
        return 3
    return 0


def get_personalized_recommendations(db: Session, current_user: User, limit: int = 5) -> list[Food]:
    liked_records = (
        db.query(FoodRecord)
        .join(Food)
        .filter(FoodRecord.user_id == current_user.id, FoodRecord.sentiment == ReviewSentiment.like)
        .order_by(FoodRecord.uploaded_at.desc())
        .all()
    )

    preferred_locations: list[str] = []
    seen_food_ids: set[int] = set()
    for record in liked_records:
        seen_food_ids.add(record.food_id)
        location = record.food.location
        if location not in preferred_locations:
            preferred_locations.append(location)

    taste_preferences = _normalize_tags(current_user.taste_preferences)
    taboo_list = _normalize_tags(current_user.taboo_list)
    spicy_level = int(current_user.spicy_level or 0)

    query = (
        db.query(Food)
        .join(FoodRecord)
        .join(User, User.id == FoodRecord.user_id)
        .filter(FoodRecord.user_id != current_user.id, User.is_private.is_(False))
    )

    candidate_foods = (
        query.group_by(Food.id)
        .order_by(func.max(FoodRecord.uploaded_at).desc(), Food.id.desc())
        .limit(60)
        .all()
    )

    scored: list[tuple[float, Food]] = []
    now = datetime.now(timezone.utc)
    for food in candidate_foods:
        if food.id in seen_food_ids:
            continue

        corpus = _food_corpus(db, food)
        if taboo_list and any(tag.lower() in corpus for tag in taboo_list):
            continue

        score = 0.0
        if preferred_locations and food.location in preferred_locations[:3]:
            score += 12 - preferred_locations.index(food.location) * 2

        if taste_preferences:
            score += sum(8 for tag in taste_preferences if tag.lower() in corpus)

        inferred_spicy = _infer_spicy_strength(corpus)
        score += max(0, 6 - abs(inferred_spicy - spicy_level) * 2)

        latest_uploaded_at = (
            db.query(func.max(FoodRecord.uploaded_at))
            .join(User, User.id == FoodRecord.user_id)
            .filter(FoodRecord.food_id == food.id, User.is_private.is_(False))
            .scalar()
        )
        if latest_uploaded_at:
            age_days = max(0, (now - _as_utc(latest_uploaded_at)).days)
            score += max(0, 10 - age_days * 0.3)

        scored.append((score, food))

    scored.sort(key=lambda item: (item[0], item[1].id), reverse=True)
    foods = [food for score, food in scored if score > 0]

    if foods:
        return foods[:limit]

    fallback_query = (
        db.query(Food)
        .join(FoodRecord)
        .join(User, User.id == FoodRecord.user_id)
        .filter(FoodRecord.user_id != current_user.id, User.is_private.is_(False))
    )
    if preferred_locations:
        fallback_query = fallback_query.filter(Food.location.in_(preferred_locations[:3]))
    if seen_food_ids:
        fallback_query = fallback_query.filter(~Food.id.in_(seen_food_ids))

    return (
        fallback_query.group_by(Food.id)
        .order_by(func.max(FoodRecord.uploaded_at).desc(), Food.id.desc())
        .limit(limit)
        .all()
    )
