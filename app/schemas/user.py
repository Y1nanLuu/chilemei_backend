from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserProfileUpdate(BaseModel):
    nickname: str | None = Field(default=None, max_length=50)
    bio: str | None = Field(default=None, max_length=255)
    avatar_url: str | None = Field(default=None, max_length=255)


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
    created_at: datetime
