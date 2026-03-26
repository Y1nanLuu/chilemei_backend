from collections import Counter, defaultdict
from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.enums import ReviewSentiment
from app.models.food_record import FoodRecord
from app.schemas.report import AnnualReportResponse, MonthlySpendItem


def build_title_tags(records: list[FoodRecord]) -> list[str]:
    if not records:
        return ["\u5e74\u5ea6\u9e3d\u5b50\u98df\u5ba2"]

    avg_price = sum(record.food.price for record in records) / len(records)
    like_ratio = sum(1 for record in records if record.sentiment == ReviewSentiment.like) / len(records)
    tags = []

    if avg_price <= Decimal('20'):
        tags.append("\u5e73\u4ef7\u7f8e\u98df\u730e\u4eba")
    if avg_price >= Decimal('50'):
        tags.append("\u8f7b\u5962\u5e72\u996d\u5bb6")
    if like_ratio >= 0.8:
        tags.append("\u4e94\u661f\u5403\u8d27")
    if len({record.food.location for record in records}) >= 5:
        tags.append("\u63a2\u5e97\u8fbe\u4eba")
    if not tags:
        tags.append("\u4f1a\u5403\u4e5f\u4f1a\u8bb0\u7684\u6821\u56ed\u98df\u5ba2")
    return tags


def generate_annual_report(db: Session, user_id: int, year: int) -> AnnualReportResponse:
    start = datetime(year, 1, 1)
    end = datetime(year + 1, 1, 1)
    records = (
        db.query(FoodRecord)
        .filter(
            FoodRecord.user_id == user_id,
            FoodRecord.uploaded_at >= start,
            FoodRecord.uploaded_at < end,
        )
        .all()
    )

    total_spend = sum((record.food.price for record in records), Decimal('0'))
    average_spend = total_spend / len(records) if records else Decimal('0')
    total_like_records = sum(1 for record in records if record.sentiment == ReviewSentiment.like)
    total_dislike_records = len(records) - total_like_records

    food_counter = Counter(record.food.name for record in records)
    location_counter = Counter(record.food.location for record in records)
    monthly = defaultdict(lambda: {'total_spend': Decimal('0'), 'record_count': 0})

    for record in records:
        bucket = monthly[record.uploaded_at.month]
        bucket['total_spend'] += record.food.price
        bucket['record_count'] += 1

    monthly_spend = [
        MonthlySpendItem(
            month=month,
            total_spend=monthly[month]['total_spend'],
            record_count=monthly[month]['record_count'],
        )
        for month in sorted(monthly)
    ]

    return AnnualReportResponse(
        year=year,
        total_records=len(records),
        total_spend=total_spend,
        average_spend=average_spend.quantize(Decimal('0.01')) if records else Decimal('0.00'),
        total_like_records=total_like_records,
        total_dislike_records=total_dislike_records,
        top_foods=[item for item, _ in food_counter.most_common(5)],
        top_locations=[item for item, _ in location_counter.most_common(5)],
        monthly_spend=monthly_spend,
        title_tags=build_title_tags(records),
    )
