from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserProfileUpdate(BaseModel):
    nickname: str | None = Field(default=None, max_length=50)
    bio: str | None = Field(default=None, max_length=255)
    avatar_url: str | None = Field(default=None, max_length=255)
    school_name: str | None = Field(default=None, max_length=100)


class PrivacySettingUpdate(BaseModel):
    is_private: bool


class UserProfile(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: EmailStr
    nickname: str
    bio: str | None
    avatar_url: str | None
    school_name: str | None
    is_private: bool
    created_at: datetime
