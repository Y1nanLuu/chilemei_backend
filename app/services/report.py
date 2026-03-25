from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.enums import DiningCategory
from app.models.food_record import FoodRecord
from app.schemas.report import AnnualReportResponse, MonthlySpendItem
from app.utils.formatters import build_location


def build_title_tags(records: list[FoodRecord]) -> list[str]:
    if not records:
        return ['年度鸽子食客']

    on_campus_count = sum(
        1 for record in records if record.dining_category == DiningCategory.on_campus
    )
    avg_price = sum(record.price for record in records) / len(records)
    tags = []

    if on_campus_count / len(records) >= 0.7:
        tags.append('食堂干饭王')
    if on_campus_count / len(records) <= 0.3:
        tags.append('校外探店达人')
    if avg_price <= Decimal('20'):
        tags.append('平价美食猎人')
    if avg_price >= Decimal('50'):
        tags.append('轻奢干饭家')
    if not tags:
        tags.append('会吃也会记的校园食客')
    return tags


def generate_annual_report(db: Session, user_id: int, year: int) -> AnnualReportResponse:
    records = (
        db.query(FoodRecord)
        .filter(
            FoodRecord.user_id == user_id,
            FoodRecord.visited_at.between(date(year, 1, 1), date(year, 12, 31)),
        )
        .all()
    )

    total_spend = sum((record.price for record in records), Decimal('0'))
    average_spend = total_spend / len(records) if records else Decimal('0')
    on_campus_count = sum(
        1 for record in records if record.dining_category == DiningCategory.on_campus
    )
    off_campus_count = len(records) - on_campus_count

    food_counter = Counter(record.food_name for record in records)
    location_counter = Counter(build_location(record) for record in records)
    monthly = defaultdict(lambda: {'total_spend': Decimal('0'), 'record_count': 0})
    budget_count = 0
    premium_count = 0

    for record in records:
        bucket = monthly[record.visited_at.month]
        bucket['total_spend'] += record.price
        bucket['record_count'] += 1
        if record.price <= Decimal('20'):
            budget_count += 1
        if record.price >= Decimal('50'):
            premium_count += 1

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
        on_campus_count=on_campus_count,
        off_campus_count=off_campus_count,
        top_foods=[item for item, _ in food_counter.most_common(5)],
        top_locations=[item for item, _ in location_counter.most_common(5)],
        budget_ratio=round(budget_count / len(records), 4) if records else 0,
        premium_ratio=round(premium_count / len(records), 4) if records else 0,
        monthly_spend=monthly_spend,
        title_tags=build_title_tags(records),
    )
