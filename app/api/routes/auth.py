import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.core.security import create_access_token, get_password_hash, verify_password
from app.models.user import User
from app.schemas.auth import (
    AuthUserInfo,
    PasswordReset,
    TokenResponse,
    UserLogin,
    UserRegister,
    WechatLoginRequest,
    WechatLoginResponse,
)

router = APIRouter()
logger = logging.getLogger(__name__)


def build_token_subject(user: User) -> str:
    return user.username if user.username else f"user:{user.id}"


@router.post('/register', response_model=TokenResponse)
def register(payload: UserRegister, db: Session = Depends(get_db)) -> TokenResponse:
    existing_user = (
        db.query(User)
        .filter((User.username == payload.username) | (User.email == payload.email))
        .first()
    )
    if existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Username or email already exists')

    user = User(
        username=payload.username,
        email=payload.email,
        password_hash=get_password_hash(payload.password),
        nickname=payload.nickname,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return TokenResponse(access_token=create_access_token(build_token_subject(user)))


@router.post('/login', response_model=TokenResponse)
def login(payload: UserLogin, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.query(User).filter(User.username == payload.username).first()
    if not user or not user.password_hash or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid username or password')

    return TokenResponse(access_token=create_access_token(build_token_subject(user)))


@router.post('/wechat-login', response_model=WechatLoginResponse)
async def wechat_login(payload: WechatLoginRequest, db: Session = Depends(get_db)) -> WechatLoginResponse:
    if not settings.wechat_app_id or not settings.wechat_app_secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='WECHAT_APP_ID / WECHAT_APP_SECRET is not configured',
        )

    params = {
        'appid': settings.wechat_app_id,
        'secret': settings.wechat_app_secret,
        'js_code': payload.code,
        'grant_type': 'authorization_code',
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(settings.wechat_code2session_url, params=params)
            response.raise_for_status()
            wx_data = response.json()
    except ValueError as exc:
        logger.exception('WeChat code2Session returned non-JSON response')
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail='WeChat code2Session returned an invalid response',
        ) from exc
    except httpx.HTTPError as exc:
        logger.exception('Failed to call WeChat code2Session API')
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail='Failed to call WeChat code2Session API',
        ) from exc

    openid = wx_data.get('openid')
    unionid = wx_data.get('unionid')
    errcode = wx_data.get('errcode')
    errmsg = wx_data.get('errmsg')

    if errcode or not openid:
        detail = f"WeChat login failed: {errmsg or 'openid not returned'}"
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)

    filters = [User.wechat_openid == openid]
    if unionid:
        filters.append(User.wechat_unionid == unionid)

    try:
        user = db.query(User).filter(or_(*filters)).first()
        is_new_user = False

        if not user:
            is_new_user = True
            nickname_suffix = openid[-6:] if len(openid) >= 6 else openid
            user = User(
                wechat_openid=openid,
                wechat_unionid=unionid,
                nickname=f'WeChatUser{nickname_suffix}',
                is_active=True,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        else:
            changed = False
            if user.wechat_openid != openid:
                user.wechat_openid = openid
                changed = True
            if unionid and user.wechat_unionid != unionid:
                user.wechat_unionid = unionid
                changed = True
            if changed:
                db.add(user)
                db.commit()
                db.refresh(user)
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception('Database error during WeChat login')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Database error during WeChat login',
        ) from exc
    except Exception as exc:
        db.rollback()
        logger.exception('Unexpected error during WeChat login')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Unexpected error during WeChat login',
        ) from exc

    access_token = create_access_token(build_token_subject(user))
    return WechatLoginResponse(
        access_token=access_token,
        user=AuthUserInfo(
            id=user.id,
            nickname=user.nickname,
            avatar_url=user.avatar_url,
            is_new_user=is_new_user,
        ),
    )


@router.post('/reset-password')
def reset_password(
    payload: PasswordReset,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    if not current_user.password_hash or not verify_password(payload.old_password, current_user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Old password is incorrect')

    current_user.password_hash = get_password_hash(payload.new_password)
    db.add(current_user)
    db.commit()
    return {'message': 'Password updated successfully'}
