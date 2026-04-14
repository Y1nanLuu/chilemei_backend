from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


def _normalize_preference_tags(value: list[str] | None) -> list[str]:
    if not value:
        return []

    normalized: list[str] = []
    seen: set[str] = set()
    for item in value:
        tag = str(item).strip()
        if not tag or tag in seen:
            continue
        seen.add(tag)
        normalized.append(tag[:30])
    return normalized[:20]


class UserProfileUpdate(BaseModel):
    nickname: str | None = Field(default=None, max_length=50)
    bio: str | None = Field(default=None, max_length=255)
    avatar_url: str | None = Field(default=None, max_length=255)


class UserPreferenceUpdate(BaseModel):
    taste_preferences: list[str] = Field(default_factory=list)
    taboo_list: list[str] = Field(default_factory=list)
    spicy_level: int = Field(ge=0, le=5)

    @field_validator('taste_preferences', 'taboo_list', mode='before')
    @classmethod
    def normalize_tags(cls, value: list[str] | None) -> list[str]:
        return _normalize_preference_tags(value)


class UserPreferenceProfile(BaseModel):
    taste_preferences: list[str] = Field(default_factory=list)
    taboo_list: list[str] = Field(default_factory=list)
    spicy_level: int = Field(default=0, ge=0, le=5)


class PrivacySettingUpdate(BaseModel):
    is_private: bool


class UserProfile(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str | None
    email: EmailStr | None
    nickname: str
    bio: str | None
    avatar_url: str | None
    is_private: bool
    taste_preferences: list[str] = Field(default_factory=list)
    taboo_list: list[str] = Field(default_factory=list)
    spicy_level: int = Field(default=0, ge=0, le=5)
    created_at: datetime

    @field_validator('taste_preferences', 'taboo_list', mode='before')
    @classmethod
    def normalize_profile_tags(cls, value: list[str] | None) -> list[str]:
        return _normalize_preference_tags(value)

    @field_validator('spicy_level', mode='before')
    @classmethod
    def normalize_spicy_level(cls, value: int | None) -> int:
        try:
            parsed = int(value if value is not None else 0)
        except (TypeError, ValueError):
            return 0
        return min(5, max(0, parsed))
