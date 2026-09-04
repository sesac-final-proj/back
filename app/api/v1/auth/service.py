import random
import secrets
import json
from datetime import datetime, timedelta, timezone
from urllib.error import URLError
from urllib.request import Request, urlopen
from urllib.parse import urlencode

import jwt
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.v1.auth.schema import (
    LoginRequest,
    PhoneVerifyRequest,
    RegionUpdateRequest,
    SignupRequest,
)
from app.core.config import settings
from app.core.redis_client import (
    check_phone_code,
    clear_phone_code,
    is_refresh_token_valid,
    revoke_refresh_token,
    save_phone_code,
    save_refresh_token,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.core.sms_client import send_sms
from app.models.region import Region
from app.models.user import SocialAccount, User, UserRole


def _unauthorized(message: str = "인증 정보가 유효하지 않습니다.") -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=message)


def _token_pair(db: Session, user: User, provider: str = "local") -> dict:
    role = user.role.value if isinstance(user.role, UserRole) else str(user.role)
    access_token = create_access_token(str(user.id), role=role, provider=provider)
    refresh_token = create_refresh_token(str(user.id), role=role, provider=provider)
    payload = decode_token(refresh_token)
    ttl_seconds = int(payload["exp"] - datetime.now(timezone.utc).timestamp())
    save_refresh_token(payload["jti"], user.id, ttl_seconds)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


def signup(db: Session, payload: SignupRequest) -> User:
    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        nickname=payload.nickname,
        nickname_set=True,  # 직접 입력한 닉네임이라 온보딩 닉네임 설정 단계가 필요 없음
        role=UserRole.USER,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="이미 사용 중인 계정입니다.") from exc
    db.refresh(user)
    return user


def login(db: Session, payload: LoginRequest) -> dict:
    user = db.scalar(select(User).where(User.email == payload.email))
    if user is None or user.password_hash is None:
        raise _unauthorized("이메일 또는 비밀번호가 올바르지 않습니다.")
    if not verify_password(payload.password, user.password_hash):
        raise _unauthorized("이메일 또는 비밀번호가 올바르지 않습니다.")
    return _token_pair(db, user)


def refresh(db: Session, refresh_token: str, required_role: str | None = None) -> dict:
    try:
        payload = decode_token(refresh_token)
    except jwt.PyJWTError:
        raise _unauthorized()

    if payload.get("type") != "refresh":
        raise _unauthorized()
    if required_role is not None and payload.get("role") != required_role:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="권한이 없습니다.")

    if not is_refresh_token_valid(payload["jti"]):
        raise _unauthorized("폐기된 refresh token입니다.")

    user = db.get(User, int(payload["sub"]))
    if user is None:
        raise _unauthorized()

    revoke_refresh_token(payload["jti"])
    return _token_pair(db, user, provider=payload.get("provider", "local"))


def logout(db: Session, refresh_token: str) -> dict:
    try:
        payload = decode_token(refresh_token)
    except jwt.PyJWTError:
        return {"message": "로그아웃되었습니다."}

    revoke_refresh_token(payload["jti"])
    return {"message": "로그아웃되었습니다."}


def update_region(db: Session, user: User, payload: RegionUpdateRequest) -> User:
    region = None
    if payload.region_id is not None:
        region = db.get(Region, payload.region_id)
    elif payload.dong_code is not None:
        region = db.scalar(select(Region).where(Region.dong_code == payload.dong_code))

    if region is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="지역을 찾을 수 없습니다.")

    user.region_id = region.id
    user.radius_m = payload.radius_m
    db.commit()
    db.refresh(user)
    return user


def send_phone_code(phone_number: str) -> None:
    code = f"{random.randint(0, 999999):06d}"
    save_phone_code(phone_number, code)
    try:
        send_sms(phone_number, f"[가지마켓] 인증번호 [{code}]를 입력해주세요.")
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="인증문자를 보내지 못했습니다."
        ) from exc


def verify_phone_code(db: Session, user: User, payload: PhoneVerifyRequest) -> User:
    if not check_phone_code(payload.phone_number, payload.code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="인증번호가 올바르지 않거나 만료됐습니다."
        )
    clear_phone_code(payload.phone_number)

    user.phone_number = payload.phone_number
    user.phone_verified = True
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="이미 등록된 전화번호입니다.") from exc
    db.refresh(user)
    return user


def update_profile_image(db: Session, user: User, profile_image_url: str | None) -> User:
    user.profile_image_url = profile_image_url
    db.commit()
    db.refresh(user)
    return user


def get_me_summary(db: Session, user: User) -> dict:
    # trades(거래분석), dream(포인트) EPIC이 아직 없어서 0으로 스텁 응답
    # (docs/issue/02-auth.md TASK-01-07 DoD: 다른 EPIC 미구현 상태에서도
    # 500 대신 안전한 값으로 응답). 해당 EPIC이 생기면 각 서비스의 집계
    # 함수를 여기서 호출하도록 교체.
    return {
        "region": user.region,
        "trade_count": 0,
        "point_balance": 0,
    }


def admin_login(db: Session, payload: LoginRequest) -> dict:
    user = db.scalar(select(User).where(User.email == payload.email, User.role == UserRole.ADMIN))
    if user is None or user.password_hash is None:
        raise _unauthorized("관리자 계정 정보가 올바르지 않습니다.")
    if not verify_password(payload.password, user.password_hash):
        raise _unauthorized("관리자 계정 정보가 올바르지 않습니다.")
    return _token_pair(db, user)


def change_admin_password(db: Session, admin: User, current_password: str, new_password: str) -> dict:
    if admin.password_hash is None or not verify_password(current_password, admin.password_hash):
        raise _unauthorized("현재 비밀번호가 올바르지 않습니다.")
    if len(new_password) < 8:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="새 비밀번호는 8자 이상이어야 합니다.")
    admin.password_hash = hash_password(new_password)
    db.commit()
    return {"message": "비밀번호가 변경되었습니다."}


def oauth_login_url(provider: str) -> dict:
    if provider == "kakao":
        params = urlencode(
            {
                "client_id": settings.kakao_client_id,
                "redirect_uri": settings.kakao_redirect_uri,
                "response_type": "code",
                "prompt": "login",
            }
        )
        return {"auth_url": f"https://kauth.kakao.com/oauth/authorize?{params}"}
    if provider == "naver":
        state = secrets.token_urlsafe(16)
        params = urlencode(
            {
                "client_id": settings.NAVER_CLIENT_ID,
                "redirect_uri": settings.naver_redirect_uri,
                "response_type": "code",
                "state": state,
                "auth_type": "reauthenticate",
            }
        )
        return {"auth_url": f"https://nid.naver.com/oauth2.0/authorize?{params}"}
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="지원하지 않는 provider입니다.")


def _post_form(url: str, data: dict, headers: dict | None = None) -> dict:
    body = urlencode(data).encode()
    request = Request(url, data=body, headers=headers or {}, method="POST")
    try:
        with urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode())
    except (OSError, URLError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="OAuth API 요청에 실패했습니다.") from exc


def _get_json(url: str, headers: dict) -> dict:
    request = Request(url, headers=headers, method="GET")
    try:
        with urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode())
    except (OSError, URLError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="OAuth API 요청에 실패했습니다.") from exc


def oauth_callback(db: Session, provider: str, code: str, state: str | None = None) -> dict:
    if provider == "kakao":
        if not settings.kakao_client_id:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Kakao OAuth 설정이 없습니다.")
        token = _post_form(
            "https://kauth.kakao.com/oauth/token",
            {
                "grant_type": "authorization_code",
                "client_id": settings.kakao_client_id,
                "client_secret": settings.KAKAO_CLIENT_SECRET,
                "redirect_uri": settings.kakao_redirect_uri,
                "code": code,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        profile = _get_json(
            "https://kapi.kakao.com/v2/user/me",
            headers={"Authorization": f"Bearer {token['access_token']}"},
        )
        account = profile.get("kakao_account", {})
        name = account.get("profile", {}).get("nickname") or f"kakao-{profile['id']}"
        return upsert_social_user(
            db,
            "kakao",
            str(profile["id"]),
            account.get("email"),
            name,
            provider_access_token=token.get("access_token"),
            provider_refresh_token=token.get("refresh_token"),
            expires_in=token.get("expires_in"),
        )

    if provider == "naver":
        if not settings.NAVER_CLIENT_ID:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Naver OAuth 설정이 없습니다.")
        token = _post_form(
            "https://nid.naver.com/oauth2.0/token",
            {
                "grant_type": "authorization_code",
                "client_id": settings.NAVER_CLIENT_ID,
                "client_secret": settings.NAVER_CLIENT_SECRET,
                "redirect_uri": settings.naver_redirect_uri,
                "code": code,
                "state": state or "",
            },
        )
        profile = _get_json(
            "https://openapi.naver.com/v1/nid/me",
            headers={"Authorization": f"Bearer {token['access_token']}"},
        )
        response = profile.get("response", {})
        name = response.get("nickname") or response.get("name") or f"naver-{response['id']}"
        return upsert_social_user(
            db,
            "naver",
            str(response["id"]),
            response.get("email"),
            name,
            provider_access_token=token.get("access_token"),
            provider_refresh_token=token.get("refresh_token"),
            expires_in=token.get("expires_in"),
        )

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="지원하지 않는 provider입니다.")


def _provider_token_expires_at(expires_in: int | str | None) -> datetime | None:
    if expires_in is None:
        return None
    try:
        seconds = int(expires_in)
    except (TypeError, ValueError):
        return None
    return datetime.now(timezone.utc) + timedelta(seconds=seconds)


def _temporary_social_nickname(db: Session, provider: str, provider_user_id: str) -> str:
    digits = "".join(char for char in provider_user_id if char.isdigit())
    seed = digits[-4:] if digits else str(abs(hash(f"{provider}:{provider_user_id}")) % 10000)
    nickname = f"사용자{seed}"[:7]
    suffix = 1
    while db.scalar(select(User.id).where(User.nickname == nickname)) is not None:
        nickname = f"사용자{suffix}"[:7]
        suffix += 1
    return nickname


def upsert_social_user(
    db: Session,
    provider: str,
    provider_user_id: str,
    email: str | None,
    name: str,
    provider_access_token: str | None = None,
    provider_refresh_token: str | None = None,
    expires_in: int | str | None = None,
) -> dict:
    account = db.scalar(
        select(SocialAccount).where(
            SocialAccount.provider == provider,
            SocialAccount.provider_user_id == provider_user_id,
        )
    )
    if account is not None:
        user = db.get(User, account.user_id)
        if user is None:
            raise _unauthorized()
        account.access_token = provider_access_token
        if provider_refresh_token:
            account.refresh_token = provider_refresh_token
        account.token_expires_at = _provider_token_expires_at(expires_in)
        db.commit()
        return _token_pair(db, user, provider=provider)

    user = User(
        email=email or f"{provider}-{provider_user_id}@social.local",
        password_hash=None,
        nickname=_temporary_social_nickname(db, provider, provider_user_id),
        role=UserRole.USER,
    )
    db.add(user)
    db.flush()
    db.add(
        SocialAccount(
            user_id=user.id,
            provider=provider,
            provider_user_id=provider_user_id,
            access_token=provider_access_token,
            refresh_token=provider_refresh_token,
            token_expires_at=_provider_token_expires_at(expires_in),
        )
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="이미 등록된 사용자입니다.") from exc
    db.refresh(user)
    return _token_pair(db, user, provider=provider)
