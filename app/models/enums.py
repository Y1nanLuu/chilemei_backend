from enum import Enum


class ReviewSentiment(str, Enum):
    like = "like"
    dislike = "dislike"
