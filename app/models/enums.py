from enum import Enum


class DiningCategory(str, Enum):
    on_campus = "on_campus"
    off_campus = "off_campus"


class ReviewSentiment(str, Enum):
    like = "like"
    dislike = "dislike"


class RatingLevel(str, Enum):
    amazing = "夯"
    top_tier = "顶级"
    premium = "人上人"
    average = "NPC"
    terrible = "拉完了"


class ReactionType(str, Enum):
    like = "like"
    dislike = "dislike"
    want_to_eat = "want_to_eat"
