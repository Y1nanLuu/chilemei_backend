from app.models.food_record import FoodRecord


def join_tags(tags: list[str]) -> str | None:
    clean_tags = [item.strip() for item in tags if item.strip()]
    return ",".join(clean_tags) if clean_tags else None


def split_tags(tags: str | None) -> list[str]:
    if not tags:
        return []
    return [item for item in tags.split(",") if item]


def build_location(record: FoodRecord) -> str:
    if record.dining_category.value == "on_campus":
        parts = [record.canteen_name, record.floor, record.window_name]
    else:
        parts = [record.store_name, record.address]
    return " / ".join([part for part in parts if part]) or "未知地点"
