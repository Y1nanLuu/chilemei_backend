from enum import Enum


class ReviewSentiment(str, Enum):
    like = "like"
    dislike = "dislike"


class RatingLevel(str, Enum):
    amazing = "?"
    top_tier = "??"
    premium = "???"
    average = "NPC"
    terrible = "???"
