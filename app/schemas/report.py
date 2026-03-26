from decimal import Decimal

from pydantic import BaseModel


class MonthlySpendItem(BaseModel):
    month: int
    total_spend: Decimal
    record_count: int


class AnnualReportResponse(BaseModel):
    year: int
    total_records: int
    total_spend: Decimal
    average_spend: Decimal
    total_like_records: int
    total_dislike_records: int
    top_foods: list[str]
    top_locations: list[str]
    monthly_spend: list[MonthlySpendItem]
    title_tags: list[str]
