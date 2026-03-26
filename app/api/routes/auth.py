from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.security import create_access_token, get_password_hash, verify_password
from app.models.user import User
from app.schemas.auth import PasswordReset, TokenResponse, UserLogin, UserRegister

router = APIRouter()


@router.post('/register', response_model=TokenResponse)
def register(payload: UserRegister, db: Session = Depends(get_db)) -> TokenResponse:
    existing_user = (
        db.query(User)
        .filter((User.username == payload.username) | (User.email == payload.email))
        .first()
    )
    if existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='\u7528\u6237\u540d\u6216\u90ae\u7bb1\u5df2\u5b58\u5728')

    user = User(
        username=payload.username,
        email=payload.email,
        password_hash=get_password_hash(payload.password),
        nickname=payload.nickname,
    )
    db.add(user)
    db.commit()

    return TokenResponse(access_token=create_access_token(user.username))


@router.post('/login', response_model=TokenResponse)
def login(payload: UserLogin, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.query(User).filter(User.username == payload.username).first()
    if not user or not user.password_hash or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='\u7528\u6237\u540d\u6216\u5bc6\u7801\u9519\u8bef')

    return TokenResponse(access_token=create_access_token(user.username))


@router.post('/reset-password')
def reset_password(
    payload: PasswordReset,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    if not current_user.password_hash or not verify_password(payload.old_password, current_user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='\u65e7\u5bc6\u7801\u9519\u8bef')

    current_user.password_hash = get_password_hash(payload.new_password)
    db.add(current_user)
    db.commit()
    return {'message': '\u5bc6\u7801\u4fee\u6539\u6210\u529f'}
