from app.models.food import Food


def build_location(food: Food) -> str:
    return food.location or "Unknown location"
