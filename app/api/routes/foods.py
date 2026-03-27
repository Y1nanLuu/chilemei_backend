from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
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
    FoodImageUploadResponse,
    FoodRankingItem,
    FoodRecordCreate,
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


def serialize_record(
    record: FoodRecord,
    food: Food,
    like_count: int = 0,
    dislike_count: int = 0,
) -> FoodRecordResponse:
    return FoodRecordResponse(
        id=record.id,
        user_id=record.user_id,
        food_id=record.food_id,
        food=FoodResponse.model_validate(food),
        sentiment=record.sentiment,
        rating_level=record.rating_level,
        review_text=record.review_text,
        image_url=record.image_url,
        uploaded_at=record.uploaded_at,
        like_count=like_count or 0,
        dislike_count=dislike_count or 0,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def get_or_create_food(db: Session, payload) -> Food:
    food = (
        db.query(Food)
        .filter(
            Food.name == payload.name,
            Food.location == payload.location,
            Food.price == payload.price,
        )
        .first()
    )
    if food:
        if payload.image_url and not food.image_url:
            food.image_url = payload.image_url
            db.add(food)
            db.flush()
        return food

    food = Food(
        name=payload.name,
        location=payload.location,
        price=payload.price,
        image_url=payload.image_url,
    )
    db.add(food)
    db.flush()
    return food


def build_public_image_url(request: Request, relative_path: str) -> str:
    base = str(request.base_url).rstrip('/')
    return f"{base}{relative_path}"


@router.post('/upload-image', response_model=FoodImageUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_food_image(
    request: Request,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
) -> FoodImageUploadResponse:
    del current_user

    suffix = Path(file.filename or '').suffix.lower()
    if suffix not in ALLOWED_IMAGE_EXTENSIONS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Unsupported image extension')
    if file.content_type not in ALLOWED_IMAGE_CONTENT_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Unsupported image content type')

    settings.food_record_media_root.mkdir(parents=True, exist_ok=True)
    unique_name = f"{uuid4().hex}{suffix}"
    stored_file = settings.food_record_media_root / unique_name

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Uploaded file is empty')

    stored_file.write_bytes(file_bytes)
    relative_path = f"{settings.media_url_prefix}/{settings.food_record_upload_dir}/{unique_name}"
    image_url = build_public_image_url(request, relative_path)

    return FoodImageUploadResponse(
        image_url=image_url,
        stored_path=stored_file.as_posix(),
        original_filename=file.filename or unique_name,
    )


@router.post('', response_model=FoodRecordResponse, status_code=status.HTTP_201_CREATED)
def create_food_record(
    payload: FoodRecordCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FoodRecordResponse:
    food = get_or_create_food(db, payload.food)
    record = FoodRecord(
        user_id=current_user.id,
        food_id=food.id,
        sentiment=payload.sentiment,
        rating_level=payload.rating_level,
        review_text=payload.review_text,
        image_url=payload.image_url,
    )
    if payload.uploaded_at is not None:
        record.uploaded_at = payload.uploaded_at
    db.add(record)
    db.commit()
    db.refresh(record)
    db.refresh(food)
    return serialize_record(record, food)


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


@router.get('/recommendations/daily', response_model=FoodRecordResponse)
def daily_recommendation(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FoodRecordResponse:
    record = get_daily_recommendation(db, current_user)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='No recommendation data')
    row = records_query(db).filter(FoodRecord.id == record.id).first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Recommended record not found')
    record, food, like_count, dislike_count = row
    return serialize_record(record, food, like_count, dislike_count)


@router.get('/recommendations/personalized', response_model=list[FoodRecordResponse])
def personalized_recommendation(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[FoodRecordResponse]:
    records = get_personalized_recommendations(db, current_user)
    if not records:
        return []
    record_ids = [record.id for record in records]
    rows = records_query(db).filter(FoodRecord.id.in_(record_ids)).all()
    row_map = {
        record.id: (record, food, like_count, dislike_count)
        for record, food, like_count, dislike_count in rows
    }
    return [serialize_record(*row_map[record_id]) for record_id in record_ids if record_id in row_map]


@router.get('/rankings', response_model=list[FoodRankingItem])
def get_rankings(
    period: str = Query(default='daily', pattern='^(daily|weekly|all)$'),
    scope: str = Query(default='global', pattern='^(global|mine)$'),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[FoodRankingItem]:
    like_expr = func.sum(case((FoodRecord.sentiment == ReviewSentiment.like, 1), else_=0))
    dislike_expr = func.sum(case((FoodRecord.sentiment == ReviewSentiment.dislike, 1), else_=0))

    query = (
        db.query(
            Food.id.label('food_id'),
            Food.name.label('food_name'),
            Food.location.label('location'),
            Food.price.label('price'),
            like_expr.label('like_count'),
            dislike_expr.label('dislike_count'),
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
        .order_by((like_expr - dislike_expr).desc(), like_expr.desc(), Food.id.desc())
        .limit(20)
        .all()
    )

    return [
        FoodRankingItem(
            food_id=row.food_id,
            food_name=row.food_name,
            location=row.location,
            price=row.price,
            like_count=row.like_count or 0,
            dislike_count=row.dislike_count or 0,
            score=(row.like_count or 0) - (row.dislike_count or 0),
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

    if payload.food is not None:
        food_update = payload.food.model_dump(exclude_unset=True)
        for field, value in food_update.items():
            setattr(record.food, field, value)
        db.add(record.food)

    update_data = payload.model_dump(exclude_unset=True, exclude={'food'})
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


@router.post('/records/{record_id}/reuse', response_model=FoodRecordResponse, status_code=status.HTTP_201_CREATED)
def reuse_food_record(
    record_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FoodRecordResponse:
    source = db.query(FoodRecord).filter(FoodRecord.id == record_id).first()
    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Source record not found')
    if source.user_id != current_user.id and source.user.is_private:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Access denied')

    new_record = FoodRecord(
        user_id=current_user.id,
        food_id=source.food_id,
        sentiment=source.sentiment,
        rating_level=source.rating_level,
        review_text=source.review_text,
        image_url=source.image_url,
    )
    db.add(new_record)
    db.commit()
    db.refresh(new_record)
    like_count, dislike_count = get_food_stats(db, new_record.food_id)
    return serialize_record(new_record, new_record.food, like_count, dislike_count)


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
