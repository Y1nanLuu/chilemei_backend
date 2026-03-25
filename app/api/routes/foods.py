from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.comment import Comment
from app.models.enums import ReactionType, ReviewSentiment
from app.models.food_record import FoodRecord
from app.models.reaction import FoodReaction
from app.models.user import User
from app.schemas.food import FoodRankingItem, FoodRecordCreate, FoodRecordResponse, FoodRecordUpdate
from app.schemas.interaction import CommentCreate, CommentResponse, ReactionCreate
from app.services.recommendation import get_daily_recommendation, get_personalized_recommendations
from app.utils.formatters import build_location, join_tags, split_tags

router = APIRouter()


LIKE_COUNT = func.sum(case((FoodReaction.reaction_type == ReactionType.like, 1), else_=0))
DISLIKE_COUNT = func.sum(case((FoodReaction.reaction_type == ReactionType.dislike, 1), else_=0))
WANT_TO_EAT_COUNT = func.sum(case((FoodReaction.reaction_type == ReactionType.want_to_eat, 1), else_=0))


def with_reaction_stats(db: Session):
    return (
        db.query(
            FoodRecord,
            LIKE_COUNT.label('like_count'),
            DISLIKE_COUNT.label('dislike_count'),
            WANT_TO_EAT_COUNT.label('want_to_eat_count'),
        )
        .outerjoin(FoodReaction, FoodReaction.food_record_id == FoodRecord.id)
        .group_by(FoodRecord.id)
    )


def serialize_record(
    record: FoodRecord,
    like_count: int = 0,
    dislike_count: int = 0,
    want_to_eat_count: int = 0,
) -> FoodRecordResponse:
    return FoodRecordResponse(
        id=record.id,
        user_id=record.user_id,
        food_name=record.food_name,
        dining_category=record.dining_category,
        canteen_name=record.canteen_name,
        floor=record.floor,
        window_name=record.window_name,
        store_name=record.store_name,
        address=record.address,
        price=record.price,
        sentiment=record.sentiment,
        rating_level=record.rating_level,
        review_text=record.review_text,
        image_url=record.image_url,
        tags=split_tags(record.tags),
        visited_at=record.visited_at,
        is_public=record.is_public,
        like_count=like_count or 0,
        dislike_count=dislike_count or 0,
        want_to_eat_count=want_to_eat_count or 0,
        created_at=record.created_at,
    )


@router.post('', response_model=FoodRecordResponse, status_code=status.HTTP_201_CREATED)
def create_food_record(
    payload: FoodRecordCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FoodRecordResponse:
    record = FoodRecord(
        user_id=current_user.id,
        **payload.model_dump(exclude={'tags'}),
        tags=join_tags(payload.tags),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return serialize_record(record)


@router.get('', response_model=list[FoodRecordResponse])
def list_food_records(
    tag: str | None = Query(default=None),
    sentiment: ReviewSentiment | None = Query(default=None),
    mine_only: bool = Query(default=False),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[FoodRecordResponse]:
    query = with_reaction_stats(db)

    if mine_only:
        query = query.filter(FoodRecord.user_id == current_user.id)
    else:
        query = query.filter(
            (FoodRecord.user_id == current_user.id) | (FoodRecord.is_public.is_(True))
        )

    if tag:
        query = query.filter(FoodRecord.tags.contains(tag))
    if sentiment:
        query = query.filter(FoodRecord.sentiment == sentiment)
    if start_date:
        query = query.filter(FoodRecord.visited_at >= start_date)
    if end_date:
        query = query.filter(FoodRecord.visited_at <= end_date)

    rows = query.order_by(FoodRecord.visited_at.desc(), FoodRecord.id.desc()).all()
    return [
        serialize_record(record, like_count, dislike_count, want_to_eat_count)
        for record, like_count, dislike_count, want_to_eat_count in rows
    ]


@router.get('/recommendations/daily', response_model=FoodRecordResponse)
def daily_recommendation(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FoodRecordResponse:
    record = get_daily_recommendation(db, current_user)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='??????')
    return serialize_record(record)


@router.get('/recommendations/personalized', response_model=list[FoodRecordResponse])
def personalized_recommendation(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[FoodRecordResponse]:
    records = get_personalized_recommendations(db, current_user)
    return [serialize_record(record) for record in records]


@router.get('/rankings', response_model=list[FoodRankingItem])
def get_rankings(
    period: str = Query(default='daily', pattern='^(daily|weekly|all)$'),
    scope: str = Query(default='global', pattern='^(global|mine)$'),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[FoodRankingItem]:
    query = with_reaction_stats(db)
    today = date.today()

    if period == 'daily':
        query = query.filter(FoodRecord.visited_at == today)
    elif period == 'weekly':
        query = query.filter(FoodRecord.visited_at >= today - timedelta(days=7))

    if scope == 'mine':
        query = query.filter(FoodRecord.user_id == current_user.id)
    else:
        query = query.filter(FoodRecord.is_public.is_(True))

    rows = query.order_by(
        (LIKE_COUNT - DISLIKE_COUNT).desc(),
        WANT_TO_EAT_COUNT.desc(),
        FoodRecord.created_at.desc(),
    ).limit(20).all()

    return [
        FoodRankingItem(
            food_record_id=record.id,
            food_name=record.food_name,
            dining_location=build_location(record),
            price=record.price,
            like_count=like_count or 0,
            dislike_count=dislike_count or 0,
            want_to_eat_count=want_to_eat_count or 0,
            score=(like_count or 0) - (dislike_count or 0),
        )
        for record, like_count, dislike_count, want_to_eat_count in rows
    ]


@router.get('/{food_id}', response_model=FoodRecordResponse)
def get_food_record(
    food_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FoodRecordResponse:
    row = with_reaction_stats(db).filter(FoodRecord.id == food_id).first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='?????')
    record, like_count, dislike_count, want_to_eat_count = row
    if record.user_id != current_user.id and not record.is_public:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='???????')
    return serialize_record(record, like_count, dislike_count, want_to_eat_count)


@router.put('/{food_id}', response_model=FoodRecordResponse)
def update_food_record(
    food_id: int,
    payload: FoodRecordUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FoodRecordResponse:
    record = (
        db.query(FoodRecord)
        .filter(FoodRecord.id == food_id, FoodRecord.user_id == current_user.id)
        .first()
    )
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='?????')

    update_data = payload.model_dump(exclude_unset=True)
    if 'tags' in update_data:
        record.tags = join_tags(update_data.pop('tags') or [])
    for field, value in update_data.items():
        setattr(record, field, value)

    db.add(record)
    db.commit()
    db.refresh(record)
    return serialize_record(record)


@router.delete('/{food_id}')
def delete_food_record(
    food_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    record = (
        db.query(FoodRecord)
        .filter(FoodRecord.id == food_id, FoodRecord.user_id == current_user.id)
        .first()
    )
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='?????')
    db.delete(record)
    db.commit()
    return {'message': '????'}


@router.post('/{food_id}/reuse', response_model=FoodRecordResponse, status_code=status.HTTP_201_CREATED)
def reuse_food_record(
    food_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FoodRecordResponse:
    source = db.query(FoodRecord).filter(FoodRecord.id == food_id).first()
    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='??????')
    if source.user_id != current_user.id and not source.is_public:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='???????')

    new_record = FoodRecord(
        user_id=current_user.id,
        food_name=source.food_name,
        dining_category=source.dining_category,
        canteen_name=source.canteen_name,
        floor=source.floor,
        window_name=source.window_name,
        store_name=source.store_name,
        address=source.address,
        price=source.price,
        sentiment=source.sentiment,
        rating_level=source.rating_level,
        review_text=source.review_text,
        image_url=source.image_url,
        tags=source.tags,
        visited_at=date.today(),
        is_public=source.is_public,
    )
    db.add(new_record)
    db.commit()
    db.refresh(new_record)
    return serialize_record(new_record)


@router.post('/{food_id}/reactions')
def react_to_food(
    food_id: int,
    payload: ReactionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    record = db.query(FoodRecord).filter(FoodRecord.id == food_id).first()
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='?????')

    existing = (
        db.query(FoodReaction)
        .filter(
            FoodReaction.user_id == current_user.id,
            FoodReaction.food_record_id == food_id,
            FoodReaction.reaction_type == payload.reaction_type,
        )
        .first()
    )
    if existing:
        db.delete(existing)
        db.commit()
        return {'message': '?????'}

    if payload.reaction_type in {ReactionType.like, ReactionType.dislike}:
        opposite = ReactionType.dislike if payload.reaction_type == ReactionType.like else ReactionType.like
        opposite_reaction = (
            db.query(FoodReaction)
            .filter(
                FoodReaction.user_id == current_user.id,
                FoodReaction.food_record_id == food_id,
                FoodReaction.reaction_type == opposite,
            )
            .first()
        )
        if opposite_reaction:
            db.delete(opposite_reaction)

    reaction = FoodReaction(
        user_id=current_user.id,
        food_record_id=food_id,
        reaction_type=payload.reaction_type,
    )
    db.add(reaction)
    db.commit()
    return {'message': '????'}


@router.post('/{food_id}/comments', response_model=CommentResponse, status_code=status.HTTP_201_CREATED)
def create_comment(
    food_id: int,
    payload: CommentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CommentResponse:
    record = db.query(FoodRecord).filter(FoodRecord.id == food_id).first()
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='?????')

    comment = Comment(user_id=current_user.id, food_record_id=food_id, content=payload.content)
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return CommentResponse.model_validate(comment)


@router.get('/{food_id}/comments', response_model=list[CommentResponse])
def list_comments(
    food_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[CommentResponse]:
    record = db.query(FoodRecord).filter(FoodRecord.id == food_id).first()
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='?????')
    if record.user_id != current_user.id and not record.is_public:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='??????')

    comments = (
        db.query(Comment)
        .filter(Comment.food_record_id == food_id)
        .order_by(Comment.created_at.desc())
        .all()
    )
    return [CommentResponse.model_validate(comment) for comment in comments]
