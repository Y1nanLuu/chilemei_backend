import random
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import case, func, or_
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.comment import Comment
from app.models.enums import ReviewSentiment
from app.models.food import Food
from app.models.food_comment import FoodComment
from app.models.food_record import FoodRecord
from app.models.user import User
from app.models.user_food_stat import UserFoodStat
from app.models.user_food_favorite import UserFoodFavorite
from app.schemas.food import (
    FoodDetailCommentResponse,
    FoodDetailResponse,
    FoodRecommendationItem,
    FoodRecordCreate,
    FoodRecordReuseDraftResponse,
    FoodRecordResponse,
    FoodRecordUpdate,
    FoodResponse,
    UserFoodFavoriteResponse,
    UserFoodStatsResponse,
)
from app.schemas.interaction import CommentCreate, CommentResponse, FoodCommentResponse, ReactionCreate
from app.services.recommendation import get_daily_recommendation, get_personalized_recommendations
from app.services.storage import (
    ObjectStorageError,
    build_food_relative_dir,
    build_public_image_url,
    ensure_image_in_food_dir,
)

router = APIRouter()


def food_stats_subquery(db: Session):
    return (
        db.query(
            UserFoodStat.food_id.label('food_id'),
            func.coalesce(func.sum(UserFoodStat.like_count), 0).label('like_count'),
            func.coalesce(func.sum(UserFoodStat.dislike_count), 0).label('dislike_count'),
        )
        .group_by(UserFoodStat.food_id)
        .subquery()
    )


def get_food_stats(db: Session, food_id: int) -> tuple[int, int]:
    row = (
        db.query(
            func.coalesce(func.sum(UserFoodStat.like_count), 0),
            func.coalesce(func.sum(UserFoodStat.dislike_count), 0),
        )
        .filter(UserFoodStat.food_id == food_id)
        .first()
    )
    return (int(row[0] or 0), int(row[1] or 0)) if row else (0, 0)


def is_food_favorited(db: Session, user_id: int, food_id: int) -> bool:
    return (
        db.query(UserFoodFavorite.id)
        .filter(UserFoodFavorite.user_id == user_id, UserFoodFavorite.food_id == food_id)
        .first()
        is not None
    )


def get_food_score(db: Session, food_id: int, current_user: User | None = None) -> float:
    query = db.query(func.avg(FoodRecord.rating_level)).join(User, User.id == FoodRecord.user_id)
    query = query.filter(FoodRecord.food_id == food_id)
    if current_user is not None:
        query = query.filter(or_(FoodRecord.user_id == current_user.id, User.is_private.is_(False)))
    else:
        query = query.filter(User.is_private.is_(False))
    score = query.scalar()
    return round(float(score or 0), 2)


def get_latest_food_description(db: Session, food_id: int, current_user: User) -> str | None:
    row = (
        db.query(FoodRecord.review_text)
        .join(User, User.id == FoodRecord.user_id)
        .filter(
            FoodRecord.food_id == food_id,
            FoodRecord.review_text.isnot(None),
            FoodRecord.review_text != '',
            or_(FoodRecord.user_id == current_user.id, User.is_private.is_(False)),
        )
        .order_by(FoodRecord.uploaded_at.desc(), FoodRecord.id.desc())
        .first()
    )
    return row[0] if row else None


def list_food_comments(db: Session, food_id: int, limit: int = 50) -> list[FoodDetailCommentResponse]:
    rows = (
        db.query(FoodComment, User.nickname.label('user_nickname'))
        .join(User, User.id == FoodComment.user_id)
        .filter(FoodComment.food_id == food_id)
        .order_by(FoodComment.created_at.desc(), FoodComment.id.desc())
        .limit(limit)
        .all()
    )
    return [
        FoodDetailCommentResponse(
            id=comment.id,
            user_id=comment.user_id,
            user_nickname=user_nickname,
            food_id=comment.food_id,
            content=comment.content,
            created_at=comment.created_at,
        )
        for comment, user_nickname in rows
    ]


def list_food_image_urls(db: Session, food: Food, current_user: User) -> list[str]:
    if not food.image_dir:
        return []

    rows = (
        db.query(FoodRecord.image_filename)
        .join(User, User.id == FoodRecord.user_id)
        .filter(
            FoodRecord.food_id == food.id,
            FoodRecord.image_filename.isnot(None),
            FoodRecord.image_filename != '',
            or_(FoodRecord.user_id == current_user.id, User.is_private.is_(False)),
        )
        .order_by(FoodRecord.uploaded_at.desc(), FoodRecord.id.desc())
        .all()
    )

    image_urls: list[str] = []
    seen: set[str] = set()
    for (image_filename,) in rows:
        if not image_filename or image_filename in seen:
            continue
        seen.add(image_filename)
        image_url = build_public_image_url(food.image_dir, image_filename)
        if image_url:
            image_urls.append(image_url)
    return image_urls


def pick_food_cover_image(db: Session, food: Food | None, current_user: User) -> str | None:
    if not food:
        return None
    image_urls = list_food_image_urls(db, food, current_user)
    if not image_urls:
        return None
    return random.choice(image_urls)


def records_query(db: Session):
    stats = food_stats_subquery(db)
    return (
        db.query(
            FoodRecord,
            Food,
            func.coalesce(stats.c.like_count, 0).label('like_count'),
            func.coalesce(stats.c.dislike_count, 0).label('dislike_count'),
        )
        .join(Food, Food.id == FoodRecord.food_id)
        .join(User, User.id == FoodRecord.user_id)
        .outerjoin(stats, stats.c.food_id == Food.id)
    )


def normalize_food_identity(name: str, location: str) -> tuple[str, str]:
    return name.strip(), location.strip()


def serialize_food_card(db: Session, food: Food, current_user: User) -> FoodRecommendationItem:
    like_count, dislike_count = get_food_stats(db, food.id)
    return FoodRecommendationItem(
        food_id=food.id,
        name=food.name,
        location=food.location,
        price=food.price,
        score=get_food_score(db, food.id, current_user),
        like_count=like_count,
        dislike_count=dislike_count,
        cover_image_url=pick_food_cover_image(db, food, current_user),
        is_favorited=is_food_favorited(db, current_user.id, food.id),
    )


def serialize_record(
    record: FoodRecord,
    food: Food,
    like_count: int = 0,
    dislike_count: int = 0,
    is_favorited: bool = False,
) -> FoodRecordResponse:
    return FoodRecordResponse(
        id=record.id,
        user_id=record.user_id,
        food_id=record.food_id,
        food=FoodResponse.model_validate(food),
        sentiment=record.sentiment,
        rating_level=record.rating_level,
        review_text=record.review_text,
        image_filename=record.image_filename,
        image_url=build_public_image_url(food.image_dir, record.image_filename),
        uploaded_at=record.uploaded_at,
        like_count=like_count or 0,
        dislike_count=dislike_count or 0,
        is_favorited=is_favorited,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def ensure_food_image_dir(db: Session, food: Food) -> Food:
    image_dir = build_food_relative_dir(food.id)
    if food.image_dir != image_dir:
        food.image_dir = image_dir
        db.add(food)
        db.flush()
    return food


def get_or_create_food(db: Session, payload: dict[str, Any]) -> Food:
    name, location = normalize_food_identity(payload['name'], payload['location'])
    food = db.query(Food).filter(Food.name == name, Food.location == location).first()
    if food:
        changed = False
        price = payload.get('price')
        if price is not None and food.price != price:
            food.price = price
            changed = True
        if changed:
            db.add(food)
            db.flush()
        return ensure_food_image_dir(db, food)

    food = Food(
        name=name,
        location=location,
        price=payload['price'],
        image_dir=None,
    )
    db.add(food)
    db.flush()
    return ensure_food_image_dir(db, food)


def resolve_food_for_record(
    db: Session,
    *,
    food_id: int | None,
    food_payload,
    base_food: Food | None = None,
) -> Food:
    if food_id is not None:
        food = db.query(Food).filter(Food.id == food_id).first()
        if not food:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Food not found')
        return ensure_food_image_dir(db, food)

    if food_payload is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Either food_id or food is required')

    food_data = food_payload.model_dump(exclude_unset=True)
    if base_food is not None:
        merged = {
            'name': base_food.name,
            'location': base_food.location,
            'price': base_food.price,
        }
        merged.update(food_data)
        food_data = merged

    missing_fields = [field for field in ('name', 'location', 'price') if food_data.get(field) is None]
    if missing_fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Missing required food fields: {', '.join(missing_fields)}",
        )

    return get_or_create_food(db, food_data)


def ensure_record_image_ready(
    food: Food,
    image_filename: str | None,
    current_user: User,
    source_food: Food | None = None,
) -> None:
    if not image_filename:
        return
    try:
        ensure_image_in_food_dir(
            food_relative_dir=food.image_dir,
            image_filename=image_filename,
            openid=current_user.wechat_openid or '',
            source_food_relative_dir=source_food.image_dir if source_food else None,
        )
    except ObjectStorageError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get('/search', response_model=list[FoodResponse])
def search_foods(
    keyword: str = Query(..., min_length=1, max_length=120),
    limit: int = Query(default=10, ge=1, le=20),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[FoodResponse]:
    del current_user

    keyword = keyword.strip()
    if not keyword:
        return []

    match_priority = case(
        (Food.name == keyword, 0),
        (Food.name.startswith(keyword), 1),
        else_=2,
    )
    foods = (
        db.query(Food)
        .filter(Food.name.contains(keyword))
        .order_by(match_priority.asc(), Food.name.asc(), Food.location.asc(), Food.id.desc())
        .limit(limit)
        .all()
    )
    return [FoodResponse.model_validate(food) for food in foods]


@router.post('', response_model=FoodRecordResponse, status_code=status.HTTP_201_CREATED)
def create_food_record(
    payload: FoodRecordCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FoodRecordResponse:
    food = resolve_food_for_record(db, food_id=payload.food_id, food_payload=payload.food)
    ensure_record_image_ready(food, payload.image_filename, current_user)

    record = FoodRecord(
        user_id=current_user.id,
        food_id=food.id,
        sentiment=payload.sentiment,
        rating_level=payload.rating_level,
        review_text=payload.review_text,
        image_filename=payload.image_filename,
    )
    if payload.uploaded_at is not None:
        record.uploaded_at = payload.uploaded_at
    db.add(record)
    db.commit()
    db.refresh(record)
    db.refresh(food)
    like_count, dislike_count = get_food_stats(db, food.id)
    return serialize_record(record, food, like_count, dislike_count, is_food_favorited(db, current_user.id, food.id))


@router.get('', response_model=list[FoodRecordResponse])
def list_food_records(
    food_name: str | None = Query(default=None),
    location: str | None = Query(default=None),
    sentiment: ReviewSentiment | None = Query(default=None),
    mine_only: bool = Query(default=False),
    start_time: datetime | None = Query(default=None),
    end_time: datetime | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[FoodRecordResponse]:
    query = records_query(db)

    if mine_only:
        query = query.filter(FoodRecord.user_id == current_user.id)
    else:
        query = query.filter(or_(FoodRecord.user_id == current_user.id, User.is_private.is_(False)))

    if food_name:
        query = query.filter(Food.name.contains(food_name))
    if location:
        query = query.filter(Food.location.contains(location))
    if sentiment:
        query = query.filter(FoodRecord.sentiment == sentiment)
    if start_time:
        query = query.filter(FoodRecord.uploaded_at >= start_time)
    if end_time:
        query = query.filter(FoodRecord.uploaded_at <= end_time)

    rows = query.order_by(FoodRecord.uploaded_at.desc(), FoodRecord.id.desc()).all()
    return [
        serialize_record(record, food, like_count, dislike_count, is_food_favorited(db, current_user.id, food.id))
        for record, food, like_count, dislike_count in rows
    ]


@router.get('/recommendations/daily', response_model=FoodRecommendationItem)
def daily_recommendation(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FoodRecommendationItem:
    food = get_daily_recommendation(db, current_user)
    if not food:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='No recommendation data')
    return serialize_food_card(db, food, current_user)


@router.get('/recommendations/personalized', response_model=list[FoodRecommendationItem])
def personalized_recommendation(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[FoodRecommendationItem]:
    foods = get_personalized_recommendations(db, current_user)
    return [serialize_food_card(db, food, current_user) for food in foods]


@router.get('/{food_id}/detail', response_model=FoodDetailResponse)
def get_food_detail(
    food_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FoodDetailResponse:
    food = db.query(Food).filter(Food.id == food_id).first()
    if not food:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Food not found')

    visible_record_exists = (
        db.query(FoodRecord.id)
        .join(User, User.id == FoodRecord.user_id)
        .filter(
            FoodRecord.food_id == food_id,
            or_(FoodRecord.user_id == current_user.id, User.is_private.is_(False)),
        )
        .first()
    )
    if not visible_record_exists:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Food not found')

    image_urls = list_food_image_urls(db, food, current_user)
    like_count, dislike_count = get_food_stats(db, food.id)
    return FoodDetailResponse(
        food_id=food.id,
        name=food.name,
        location=food.location,
        price=food.price,
        score=get_food_score(db, food.id, current_user),
        like_count=like_count,
        dislike_count=dislike_count,
        cover_image_url=random.choice(image_urls) if image_urls else None,
        image_urls=image_urls,
        is_favorited=is_food_favorited(db, current_user.id, food.id),
        description=get_latest_food_description(db, food.id, current_user),
        comments=list_food_comments(db, food.id),
    )


@router.get('/rankings', response_model=list[FoodRecommendationItem])
def get_rankings(
    period: str = Query(default='daily', pattern='^(daily|weekly|all)$'),
    scope: str = Query(default='global', pattern='^(global|mine)$'),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[FoodRecommendationItem]:
    like_expr = func.sum(case((FoodRecord.sentiment == ReviewSentiment.like, 1), else_=0))
    dislike_expr = func.sum(case((FoodRecord.sentiment == ReviewSentiment.dislike, 1), else_=0))
    score_expr = func.avg(FoodRecord.rating_level)

    query = (
        db.query(
            Food.id.label('food_id'),
            Food.name.label('food_name'),
            Food.location.label('location'),
            Food.price.label('price'),
            like_expr.label('like_count'),
            dislike_expr.label('dislike_count'),
            score_expr.label('score'),
        )
        .join(FoodRecord, FoodRecord.food_id == Food.id)
        .join(User, User.id == FoodRecord.user_id)
    )

    now = datetime.now(timezone.utc)
    if period == 'daily':
        query = query.filter(FoodRecord.uploaded_at >= now - timedelta(days=1))
    elif period == 'weekly':
        query = query.filter(FoodRecord.uploaded_at >= now - timedelta(days=7))

    if scope == 'mine':
        query = query.filter(FoodRecord.user_id == current_user.id)
    else:
        query = query.filter(or_(FoodRecord.user_id == current_user.id, User.is_private.is_(False)))

    rows = (
        query.group_by(Food.id, Food.name, Food.location, Food.price)
        .order_by(score_expr.desc(), like_expr.desc(), dislike_expr.asc(), Food.id.desc())
        .limit(20)
        .all()
    )

    foods = {food.id: food for food in db.query(Food).filter(Food.id.in_([row.food_id for row in rows])).all()} if rows else {}
    return [
        FoodRecommendationItem(
            food_id=row.food_id,
            name=row.food_name,
            location=row.location,
            price=row.price,
            score=round(float(row.score or 0), 2),
            like_count=row.like_count or 0,
            dislike_count=row.dislike_count or 0,
            cover_image_url=pick_food_cover_image(db, foods.get(row.food_id), current_user),
            is_favorited=is_food_favorited(db, current_user.id, row.food_id),
        )
        for row in rows
    ]


@router.post('/{food_id}/comments', response_model=FoodCommentResponse, status_code=status.HTTP_201_CREATED)
def create_food_comment(
    food_id: int,
    payload: CommentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FoodCommentResponse:
    food = db.query(Food).filter(Food.id == food_id).first()
    if not food:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Food not found')

    comment = FoodComment(user_id=current_user.id, food_id=food_id, content=payload.content)
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return FoodCommentResponse(
        id=comment.id,
        user_id=comment.user_id,
        user_nickname=current_user.nickname,
        food_id=comment.food_id,
        content=comment.content,
        created_at=comment.created_at,
    )


@router.get('/{food_id}/comments', response_model=list[FoodCommentResponse])
def list_food_card_comments(
    food_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[FoodCommentResponse]:
    del current_user
    food = db.query(Food).filter(Food.id == food_id).first()
    if not food:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Food not found')

    rows = (
        db.query(FoodComment, User.nickname.label('user_nickname'))
        .join(User, User.id == FoodComment.user_id)
        .filter(FoodComment.food_id == food_id)
        .order_by(FoodComment.created_at.desc(), FoodComment.id.desc())
        .all()
    )
    return [
        FoodCommentResponse(
            id=comment.id,
            user_id=comment.user_id,
            user_nickname=user_nickname,
            food_id=comment.food_id,
            content=comment.content,
            created_at=comment.created_at,
        )
        for comment, user_nickname in rows
    ]


@router.get('/favorites', response_model=list[FoodRecommendationItem])
def list_favorite_foods(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[FoodRecommendationItem]:
    foods = (
        db.query(Food)
        .join(UserFoodFavorite, UserFoodFavorite.food_id == Food.id)
        .filter(UserFoodFavorite.user_id == current_user.id)
        .order_by(UserFoodFavorite.created_at.desc(), UserFoodFavorite.id.desc())
        .all()
    )
    return [serialize_food_card(db, food, current_user) for food in foods]


@router.post('/{food_id}/favorite', response_model=UserFoodFavoriteResponse)
def favorite_food(
    food_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserFoodFavoriteResponse:
    food = db.query(Food).filter(Food.id == food_id).first()
    if not food:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Food not found')

    favorite = (
        db.query(UserFoodFavorite)
        .filter(UserFoodFavorite.user_id == current_user.id, UserFoodFavorite.food_id == food_id)
        .first()
    )
    if not favorite:
        favorite = UserFoodFavorite(user_id=current_user.id, food_id=food_id)
        db.add(favorite)
        db.commit()

    return UserFoodFavoriteResponse(user_id=current_user.id, food_id=food_id, is_favorited=True)


@router.delete('/{food_id}/favorite', response_model=UserFoodFavoriteResponse)
def unfavorite_food(
    food_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserFoodFavoriteResponse:
    food = db.query(Food).filter(Food.id == food_id).first()
    if not food:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Food not found')

    favorite = (
        db.query(UserFoodFavorite)
        .filter(UserFoodFavorite.user_id == current_user.id, UserFoodFavorite.food_id == food_id)
        .first()
    )
    if favorite:
        db.delete(favorite)
        db.commit()

    return UserFoodFavoriteResponse(user_id=current_user.id, food_id=food_id, is_favorited=False)


@router.get('/records/{record_id}', response_model=FoodRecordResponse)
def get_food_record(
    record_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FoodRecordResponse:
    row = records_query(db).filter(FoodRecord.id == record_id).first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Record not found')
    record, food, like_count, dislike_count = row
    if record.user_id != current_user.id and record.user.is_private:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Access denied')
    return serialize_record(record, food, like_count, dislike_count, is_food_favorited(db, current_user.id, food.id))


@router.put('/records/{record_id}', response_model=FoodRecordResponse)
def update_food_record(
    record_id: int,
    payload: FoodRecordUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FoodRecordResponse:
    record = (
        db.query(FoodRecord)
        .filter(FoodRecord.id == record_id, FoodRecord.user_id == current_user.id)
        .first()
    )
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Record not found')

    source_food = record.food
    if payload.food_id is not None or payload.food is not None:
        food = resolve_food_for_record(
            db,
            food_id=payload.food_id,
            food_payload=payload.food,
            base_food=record.food,
        )
        record.food_id = food.id

    update_data = payload.model_dump(exclude_unset=True, exclude={'food', 'food_id'})
    for field, value in update_data.items():
        setattr(record, field, value)

    ensure_record_image_ready(record.food, record.image_filename, current_user, source_food)

    db.add(record)
    db.commit()
    db.refresh(record)
    db.refresh(record.food)
    like_count, dislike_count = get_food_stats(db, record.food_id)
    return serialize_record(record, record.food, like_count, dislike_count, is_food_favorited(db, current_user.id, record.food_id))


@router.delete('/records/{record_id}')
def delete_food_record(
    record_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    record = (
        db.query(FoodRecord)
        .filter(FoodRecord.id == record_id, FoodRecord.user_id == current_user.id)
        .first()
    )
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Record not found')
    db.delete(record)
    db.commit()
    return {'message': 'Deleted successfully'}


@router.post('/records/{record_id}/reuse', response_model=FoodRecordReuseDraftResponse)
def reuse_food_record(
    record_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FoodRecordReuseDraftResponse:
    source = db.query(FoodRecord).filter(FoodRecord.id == record_id).first()
    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Source record not found')
    if source.user_id != current_user.id and source.user.is_private:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Access denied')

    return FoodRecordReuseDraftResponse(
        source_record_id=source.id,
        food_id=source.food_id,
        food=FoodResponse.model_validate(source.food),
        sentiment=source.sentiment,
        rating_level=source.rating_level,
        review_text=source.review_text,
        image_filename=source.image_filename,
        image_url=build_public_image_url(source.food.image_dir, source.image_filename),
    )


@router.post('/{food_id}/reactions', response_model=UserFoodStatsResponse)
def react_to_food(
    food_id: int,
    payload: ReactionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserFoodStatsResponse:
    food = db.query(Food).filter(Food.id == food_id).first()
    if not food:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Food not found')

    stats = (
        db.query(UserFoodStat)
        .filter(UserFoodStat.user_id == current_user.id, UserFoodStat.food_id == food_id)
        .first()
    )
    if not stats:
        stats = UserFoodStat(user_id=current_user.id, food_id=food_id, like_count=0, dislike_count=0)

    if payload.reaction_type == ReviewSentiment.like:
        stats.like_count += 1
    else:
        stats.dislike_count += 1

    db.add(stats)
    db.commit()
    db.refresh(stats)
    return UserFoodStatsResponse(
        user_id=stats.user_id,
        food_id=stats.food_id,
        like_count=stats.like_count,
        dislike_count=stats.dislike_count,
    )


@router.post('/records/{record_id}/comments', response_model=CommentResponse, status_code=status.HTTP_201_CREATED)
def create_comment(
    record_id: int,
    payload: CommentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CommentResponse:
    record = db.query(FoodRecord).filter(FoodRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Record not found')

    comment = Comment(user_id=current_user.id, food_record_id=record_id, content=payload.content)
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return CommentResponse.model_validate(comment)


@router.get('/records/{record_id}/comments', response_model=list[CommentResponse])
def list_comments(
    record_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[CommentResponse]:
    record = db.query(FoodRecord).filter(FoodRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Record not found')
    if record.user_id != current_user.id and record.user.is_private:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Cannot view comments')

    comments = (
        db.query(Comment)
        .filter(Comment.food_record_id == record_id)
        .order_by(Comment.created_at.desc())
        .all()
    )
    return [CommentResponse.model_validate(comment) for comment in comments]
