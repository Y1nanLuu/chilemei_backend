from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.user import (
    PrivacySettingUpdate,
    UserPreferenceProfile,
    UserPreferenceUpdate,
    UserProfile,
    UserProfileUpdate,
)

router = APIRouter()


def serialize_user_profile(user: User) -> UserProfile:
    return UserProfile.model_validate(user)


def serialize_user_preferences(user: User) -> UserPreferenceProfile:
    return UserPreferenceProfile(
        taste_preferences=user.taste_preferences or [],
        taboo_list=user.taboo_list or [],
        spicy_level=user.spicy_level or 0,
    )


@router.get('/me', response_model=UserProfile)
def get_me(current_user: User = Depends(get_current_user)) -> UserProfile:
    return serialize_user_profile(current_user)


@router.put('/me', response_model=UserProfile)
def update_me(
    payload: UserProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserProfile:
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(current_user, field, value)
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return serialize_user_profile(current_user)


@router.put('/me/preferences', response_model=UserPreferenceProfile)
def update_me_preferences(
    payload: UserPreferenceUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserPreferenceProfile:
    current_user.taste_preferences = payload.taste_preferences
    current_user.taboo_list = payload.taboo_list
    current_user.spicy_level = payload.spicy_level
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return serialize_user_preferences(current_user)


@router.put('/me/privacy', response_model=UserProfile)
def update_privacy(
    payload: PrivacySettingUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserProfile:
    current_user.is_private = payload.is_private
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return serialize_user_profile(current_user)
