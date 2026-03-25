from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.user import PrivacySettingUpdate, UserProfile, UserProfileUpdate

router = APIRouter()


@router.get('/me', response_model=UserProfile)
def get_me(current_user: User = Depends(get_current_user)) -> UserProfile:
    return UserProfile.model_validate(current_user)


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
    return UserProfile.model_validate(current_user)


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
    return UserProfile.model_validate(current_user)
