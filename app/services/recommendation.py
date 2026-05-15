import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from math import log1p
from typing import Any, Iterable

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.food import Food
from app.models.food_comment import FoodComment
from app.models.food_record import FoodRecord
from app.models.user import User
from app.models.user_food_favorite import UserFoodFavorite
from app.models.user_food_stat import UserFoodStat

SPICY_KEYWORDS: dict[int, tuple[str, ...]] = {
    0: ('不辣', '清淡'),
    1: ('微辣',),
    2: ('小辣',),
    3: ('中辣', '酸辣'),
    4: ('麻辣', '香辣', '川菜', '火锅'),
    5: ('爆辣', '特辣', '无辣不欢'),
}
GENERIC_SPICY_TERMS = ('辣', '麻辣', '香辣', '酸辣', '川菜', '火锅')
TAG_FIELDS = (
    'taste_preferences',
    'cuisines',
    'ingredients',
    'seasonings',
    'cooking_methods',
    'texture_tags',
    'scenario_tags',
    'recommendation_tags',
    'health_tags',
)


@dataclass(frozen=True)
class RecommendationWeights:
    heat: float
    taste: float
    freshness: float
    preference: float
    exploration: float


@dataclass(frozen=True)
class FoodRecommendationScore:
    food: Food
    total_score: float
    heat_score: float
    taste_score: float
    freshness_score: float
    preference_score: float
    exploration_score: float


GUESS_YOU_LIKE_WEIGHTS = RecommendationWeights(
    heat=0.22,
    taste=0.18,
    freshness=0.15,
    preference=0.38,
    exploration=0.07,
)
TODAY_WEIGHTS = RecommendationWeights(
    heat=0.36,
    taste=0.25,
    freshness=0.22,
    preference=0.07,
    exploration=0.10,
)


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


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


def _safe_max(values: Iterable[float], default: float = 0.0) -> float:
    result = max(values, default=default)
    return result if result > 0 else default


def _normalize(value: float, max_value: float) -> float:
    if max_value <= 0:
        return 0.0
    return min(100.0, max(0.0, value / max_value * 100))


def _food_tags(food: Food) -> dict[str, Any]:
    return food.food_tags if isinstance(food.food_tags, dict) else {}


def _food_tag_values(food: Food) -> list[str]:
    tags = _food_tags(food)
    values: list[str] = []
    for field in TAG_FIELDS:
        field_values = tags.get(field) or []
        if isinstance(field_values, list):
            values.extend(str(value).strip() for value in field_values if str(value).strip())
    summary = str(tags.get('summary') or '').strip()
    if summary:
        values.append(summary)
    return _normalize_tags(values)


def _food_corpus(food: Food) -> str:
    return ' '.join([food.name, food.location, *_food_tag_values(food)]).lower()


def _infer_spicy_strength(food: Food) -> int:
    tags = _food_tags(food)
    if tags.get('chili_level') is not None:
        try:
            return max(0, min(5, int(tags.get('chili_level') or 0)))
        except (TypeError, ValueError):
            pass

    corpus = _food_corpus(food)
    for level in range(5, -1, -1):
        if any(keyword.lower() in corpus for keyword in SPICY_KEYWORDS[level]):
            return level
    if any(keyword.lower() in corpus for keyword in GENERIC_SPICY_TERMS):
        return 3
    return 0


def _preference_score(food: Food, current_user: User) -> float:
    corpus = _food_corpus(food)
    preferences = _normalize_tags(current_user.taste_preferences)

    score = 0.0
    if preferences:
        matched_count = sum(1 for tag in preferences if tag.lower() in corpus)
        score += min(70.0, matched_count / len(preferences) * 70)

    spicy_level = int(current_user.spicy_level or 0)
    spicy_distance = abs(_infer_spicy_strength(food) - spicy_level)
    score += max(0.0, 30.0 - spicy_distance * 6)
    return min(100.0, score)


def _matches_taboo(food: Food, current_user: User) -> bool:
    taboos = _normalize_tags(current_user.taboo_list)
    if not taboos:
        return False
    corpus = _food_corpus(food)
    return any(taboo.lower() in corpus for taboo in taboos)


def _latest_interaction_at(food: Food, latest_record_at: datetime | None, latest_favorite_at: datetime | None) -> datetime | None:
    dates = [
        _as_utc(date)
        for date in (food.created_at, latest_record_at, latest_favorite_at)
        if date is not None
    ]
    if not dates:
        return None
    return max(dates)


def build_recommendation_scores(
    db: Session,
    current_user: User,
    weights: RecommendationWeights,
) -> list[FoodRecommendationScore]:
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)

    stats_rows = (
        db.query(
            UserFoodStat.food_id,
            func.coalesce(func.sum(UserFoodStat.like_count), 0).label('like_count'),
        )
        .group_by(UserFoodStat.food_id)
        .all()
    )
    favorite_rows = (
        db.query(
            UserFoodFavorite.food_id,
            func.count(UserFoodFavorite.id).label('favorite_count'),
            func.max(UserFoodFavorite.created_at).label('latest_favorite_at'),
        )
        .group_by(UserFoodFavorite.food_id)
        .all()
    )
    rating_rows = (
        db.query(
            FoodRecord.food_id,
            func.avg(FoodRecord.rating_level).label('avg_rating'),
            func.max(FoodRecord.uploaded_at).label('latest_record_at'),
        )
        .group_by(FoodRecord.food_id)
        .all()
    )
    recent_record_rows = (
        db.query(FoodRecord.food_id, func.count(FoodRecord.id).label('record_count'))
        .filter(FoodRecord.uploaded_at >= week_ago)
        .group_by(FoodRecord.food_id)
        .all()
    )
    recent_favorite_rows = (
        db.query(UserFoodFavorite.food_id, func.count(UserFoodFavorite.id).label('favorite_count'))
        .filter(UserFoodFavorite.created_at >= week_ago)
        .group_by(UserFoodFavorite.food_id)
        .all()
    )
    recent_stat_rows = (
        db.query(
            UserFoodStat.food_id,
            func.coalesce(func.sum(UserFoodStat.like_count + UserFoodStat.dislike_count), 0).label('reaction_count'),
        )
        .filter(UserFoodStat.updated_at >= week_ago)
        .group_by(UserFoodStat.food_id)
        .all()
    )
    recent_comment_rows = (
        db.query(FoodComment.food_id, func.count(FoodComment.id).label('comment_count'))
        .filter(FoodComment.created_at >= week_ago)
        .group_by(FoodComment.food_id)
        .all()
    )

    like_counts = {row.food_id: int(row.like_count or 0) for row in stats_rows}
    favorite_counts = {row.food_id: int(row.favorite_count or 0) for row in favorite_rows}
    latest_favorite_at = {row.food_id: row.latest_favorite_at for row in favorite_rows}
    avg_ratings = {row.food_id: float(row.avg_rating or 0) for row in rating_rows}
    latest_record_at = {row.food_id: row.latest_record_at for row in rating_rows}

    recent_interactions: dict[int, int] = {}
    for rows, attr in (
        (recent_record_rows, 'record_count'),
        (recent_favorite_rows, 'favorite_count'),
        (recent_stat_rows, 'reaction_count'),
        (recent_comment_rows, 'comment_count'),
    ):
        for row in rows:
            recent_interactions[row.food_id] = recent_interactions.get(row.food_id, 0) + int(getattr(row, attr) or 0)

    raw_heat = {
        food_id: log1p(like_counts.get(food_id, 0) * 2 + favorite_counts.get(food_id, 0) * 3)
        for food_id in set(like_counts) | set(favorite_counts)
    }
    max_heat = _safe_max(raw_heat.values())
    max_recent = _safe_max(float(value) for value in recent_interactions.values())

    foods = db.query(Food).all()
    scores: list[FoodRecommendationScore] = []
    for food in foods:
        if _matches_taboo(food, current_user):
            continue

        heat_score = _normalize(raw_heat.get(food.id, 0.0), max_heat)
        taste_score = _normalize(avg_ratings.get(food.id, 0.0), 5.0)
        freshness_score = _normalize(float(recent_interactions.get(food.id, 0)), max_recent)
        preference_score = _preference_score(food, current_user)

        interaction_total = like_counts.get(food.id, 0) + favorite_counts.get(food.id, 0) + recent_interactions.get(food.id, 0)
        cold_bonus = 70.0 / (1.0 + interaction_total)
        latest_at = _latest_interaction_at(food, latest_record_at.get(food.id), latest_favorite_at.get(food.id))
        new_bonus = 0.0
        if latest_at:
            age_days = max(0, (datetime.now(timezone.utc) - _as_utc(latest_at)).days)
            new_bonus = max(0.0, 30.0 - age_days * 4)
        exploration_score = min(100.0, cold_bonus + new_bonus + random.uniform(0, 12))

        total_score = (
            heat_score * weights.heat
            + taste_score * weights.taste
            + freshness_score * weights.freshness
            + preference_score * weights.preference
            + exploration_score * weights.exploration
        )
        scores.append(
            FoodRecommendationScore(
                food=food,
                total_score=total_score,
                heat_score=heat_score,
                taste_score=taste_score,
                freshness_score=freshness_score,
                preference_score=preference_score,
                exploration_score=exploration_score,
            )
        )

    scores.sort(key=lambda item: (item.total_score, item.food.id), reverse=True)
    return scores


def _dedupe_scores(scores: Iterable[FoodRecommendationScore]) -> list[FoodRecommendationScore]:
    result: list[FoodRecommendationScore] = []
    seen: set[int] = set()
    for score in scores:
        if score.food.id in seen:
            continue
        seen.add(score.food.id)
        result.append(score)
    return result


def get_guess_you_like_recommendations(db: Session, current_user: User, limit: int = 10) -> list[Food]:
    scores = build_recommendation_scores(db, current_user, GUESS_YOU_LIKE_WEIGHTS)
    if limit <= 0:
        return []

    exploration_count = 1 if limit >= 4 else 0
    exploration_count = max(exploration_count, int(limit * 0.2))
    main_count = max(0, limit - exploration_count)

    main_scores = scores[:main_count]
    exploration_pool = sorted(
        scores[main_count:],
        key=lambda item: (item.exploration_score, item.preference_score, item.food.id),
        reverse=True,
    )
    result = _dedupe_scores([*main_scores, *exploration_pool[:exploration_count]])
    return [score.food for score in result[:limit]]


def get_today_recommendations(db: Session, current_user: User) -> list[Food]:
    scores = build_recommendation_scores(db, current_user, TODAY_WEIGHTS)
    hot_scores = sorted(
        scores,
        key=lambda item: (item.heat_score, item.taste_score, item.freshness_score, item.food.id),
        reverse=True,
    )
    cold_scores = sorted(
        scores,
        key=lambda item: (item.exploration_score, -item.heat_score, item.food.id),
        reverse=True,
    )

    result = _dedupe_scores([*hot_scores[:3], *cold_scores])
    return [score.food for score in result[:4]]


def get_daily_recommendation(db: Session, current_user: User | None = None) -> Food | None:
    if current_user is None:
        current_user = User(nickname='')
    foods = get_today_recommendations(db, current_user)
    return foods[0] if foods else None


def get_personalized_recommendations(db: Session, current_user: User, limit: int = 10) -> list[Food]:
    return get_guess_you_like_recommendations(db, current_user, limit)
