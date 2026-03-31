import random
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import case, func, or_
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.models.comment import Comment
from app.models.enums import ReviewSentiment
from app.models.food import Food
from app.models.food_record import FoodRecord
from app.models.user import User
from app.models.user_food_stat import UserFoodStat
from app.schemas.food import (
    FoodDetailCommentResponse,
    FoodDetailResponse,
    FoodImageUploadResponse,
    FoodRankingItem,
    FoodRecommendationItem,
    FoodRecordCreate,
    FoodRecordReuseDraftResponse,
    FoodRecordResponse,
    FoodRecordUpdate,
    FoodResponse,
    UserFoodStatsResponse,
)
from app.schemas.interaction import CommentCreate, CommentResponse, ReactionCreate
from app.services.recommendation import get_daily_recommendation, get_personalized_recommendations

router = APIRouter()
ALLOWED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}
ALLOWED_IMAGE_CONTENT_TYPES = {
    'image/jpeg',
    'image/png',
    'image/webp',
    'image/gif',
}


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


def list_food_comments(db: Session, food_id: int, current_user: User, limit: int = 50) -> list[FoodDetailCommentResponse]:
    rows = (
        db.query(Comment, User.nickname.label('user_nickname'))
        .join(User, User.id == Comment.user_id)
        .join(FoodRecord, FoodRecord.id == Comment.food_record_id)
        .filter(
            FoodRecord.food_id == food_id,
            or_(FoodRecord.user_id == current_user.id, FoodRecord.user.has(User.is_private.is_(False))),
        )
        .order_by(Comment.created_at.desc(), Comment.id.desc())
        .limit(limit)
        .all()
    )
    return [
        FoodDetailCommentResponse(
            id=comment.id,
            user_id=comment.user_id,
            user_nickname=user_nickname,
            food_record_id=comment.food_record_id,
            content=comment.content,
            created_at=comment.created_at,
        )
        for comment, user_nickname in rows
    ]


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


def normalize_relative_path(path: str) -> str:
    return path.replace('\\', '/').strip('/')


def build_food_image_dir(food_id: int) -> str:
    return normalize_relative_path(f"{settings.food_upload_dir}/{food_id}")


def build_media_url(relative_path: str) -> str:
    return f"{settings.media_url_prefix}/{normalize_relative_path(relative_path)}"


def build_record_relative_path(food: Food, image_filename: str | None) -> str | None:
    if not food.image_dir or not image_filename:
        return None
    return normalize_relative_path(f"{food.image_dir}/{image_filename}")


def list_food_image_urls(food: Food) -> list[str]:
    if not food.image_dir:
        return []
    image_dir = settings.media_root / Path(food.image_dir)
    if not image_dir.exists() or not image_dir.is_dir():
        return []
    image_paths = [
        item for item in image_dir.iterdir()
        if item.is_file() and item.suffix.lower() in ALLOWED_IMAGE_EXTENSIONS
    ]
    image_paths.sort(key=lambda item: item.name)
    return [build_media_url(normalize_relative_path(f"{food.image_dir}/{item.name}")) for item in image_paths]


def pick_food_cover_image(food: Food) -> str | None:
    image_urls = list_food_image_urls(food)
    if not image_urls:
        return None
    return random.choice(image_urls)


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
        cover_image_url=pick_food_cover_image(food),
    )


def serialize_record(
    record: FoodRecord,
    food: Food,
    like_count: int = 0,
    dislike_count: int = 0,
) -> FoodRecordResponse:
    relative_path = build_record_relative_path(food, record.image_filename)
    return FoodRecordResponse(
        id=record.id,
        user_id=record.user_id,
        food_id=record.food_id,
        food=FoodResponse.model_validate(food),
        sentiment=record.sentiment,
        rating_level=record.rating_level,
        review_text=record.review_text,
        image_filename=record.image_filename,
        image_url=build_media_url(relative_path) if relative_path else None,
        uploaded_at=record.uploaded_at,
        like_count=like_count or 0,
        dislike_count=dislike_count or 0,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def ensure_food_image_dir(db: Session, food: Food) -> Food:
    image_dir = build_food_image_dir(food.id)
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


@router.post('/upload-image', response_model=FoodImageUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_food_image(
    file: UploadFile = File(...),
    food_id: int | None = Form(default=None),
    food_name: str | None = Form(default=None),
    location: str | None = Form(default=None),
    price: Decimal | None = Form(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FoodImageUploadResponse:
    del current_user

    suffix = Path(file.filename or '').suffix.lower()
    if suffix not in ALLOWED_IMAGE_EXTENSIONS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Unsupported image extension')
    if file.content_type not in ALLOWED_IMAGE_CONTENT_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Unsupported image content type')

    if food_id is not None:
        food = db.query(Food).filter(Food.id == food_id).first()
        if not food:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Food not found')
        food = ensure_food_image_dir(db, food)
    else:
        if not food_name or not location or price is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Provide food_id, or provide food_name, location, and price',
            )
        food = get_or_create_food(
            db,
            {'name': food_name, 'location': location, 'price': price},
        )

    target_dir = settings.media_root / Path(food.image_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    image_filename = f"{uuid4().hex}{suffix}"
    stored_file = target_dir / image_filename

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Uploaded file is empty')

    stored_file.write_bytes(file_bytes)
    db.commit()
    relative_file_path = normalize_relative_path(f"{food.image_dir}/{image_filename}")

    return FoodImageUploadResponse(
        image_dir=food.image_dir,
        image_filename=image_filename,
        image_url=build_media_url(relative_file_path),
        stored_path=relative_file_path,
        original_filename=file.filename or image_filename,
    )


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
    return serialize_record(record, food, like_count, dislike_count)


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
        serialize_record(record, food, like_count, dislike_count)
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

    image_urls = list_food_image_urls(food)
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
        description=get_latest_food_description(db, food.id, current_user),
        comments=list_food_comments(db, food.id, current_user),
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
    )

    now = datetime.now(timezone.utc)
    if period == 'daily':
        query = query.filter(FoodRecord.uploaded_at >= now - timedelta(days=1))
    elif period == 'weekly':
        query = query.filter(FoodRecord.uploaded_at >= now - timedelta(days=7))

    if scope == 'mine':
        query = query.filter(FoodRecord.user_id == current_user.id)

    rows = (
        query.group_by(Food.id, Food.name, Food.location, Food.price)
        .order_by(score_expr.desc(), like_expr.desc(), dislike_expr.asc(), Food.id.desc())
        .limit(20)
        .all()
    )

    return [
        FoodRecommendationItem(
            food_id=row.food_id,
            name=row.food_name,
            location=row.location,
            price=row.price,
            score=round(float(row.score or 0), 2),
            like_count=row.like_count or 0,
            dislike_count=row.dislike_count or 0,
            cover_image_url=pick_food_cover_image(db.query(Food).filter(Food.id == row.food_id).first()),
        )
        for row in rows
    ]


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
    return serialize_record(record, food, like_count, dislike_count)


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

    db.add(record)
    db.commit()
    db.refresh(record)
    db.refresh(record.food)
    like_count, dislike_count = get_food_stats(db, record.food_id)
    return serialize_record(record, record.food, like_count, dislike_count)


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

    relative_path = build_record_relative_path(source.food, source.image_filename)
    return FoodRecordReuseDraftResponse(
        source_record_id=source.id,
        food_id=source.food_id,
        food=FoodResponse.model_validate(source.food),
        sentiment=source.sentiment,
        rating_level=source.rating_level,
        review_text=source.review_text,
        image_filename=source.image_filename,
        image_url=build_media_url(relative_path) if relative_path else None,
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