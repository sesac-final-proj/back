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
    ProfileUpdateRequest,
    RegionUpdateRequest,
    SignupRequest,
    UserRegionCreateRequest,
    UserRegionItem,
    UserRegionListResponse,
    UserRegionUpdateRequest,
)
from app.core.config import settings
from app.core.redis_client import is_refresh_token_valid, revoke_refresh_token, save_refresh_token
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.block import UserBlock
from app.models.favorite import ProductFavorite
from app.models.recently_viewed import RecentlyViewedProduct
from app.models.region import Region
from app.models.user import RefreshToken, SocialAccount, User, UserRole
from app.models.user_region import UserRegion

# PRD MVP는 "영등포-노원-송파 활동동네 및 거래반경 설정"까지만 요구 — 다건 등록은
# 당근 실제 앱처럼 최대 2개로 제한한다(docs/issue/11-multi-region.md). 정책이
# 바뀌면 이 값만 조정.
MAX_USER_REGIONS = 2


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


def withdraw_account(db: Session, user: User, refresh_token: str | None) -> dict:
    """회원 탈퇴. 본인만 보는 데이터(찜/최근본/동네/소셜연동/차단목록)는 완전 삭제하고,
    다른 유저와 얽힌 데이터(채팅/판매글)는 지우지 않는다 — 채팅방이나 판매글을 지우면
    상대방 쪽 대화 기록/거래 내역까지 같이 깨지기 때문. 대신 유저 row는 남기되 로그인
    불가능한 상태로 익명화해서, 이후 어디서든(채팅/판매글) 닉네임을 조회하면 자동으로
    "탈퇴회원"으로 보이게 한다 (get_product_detail의 seller_nickname 조회와 동일한 패턴).
    """
    if refresh_token:
        try:
            payload = decode_token(refresh_token)
            revoke_refresh_token(payload["jti"])
        except jwt.PyJWTError:
            pass

    db.query(RefreshToken).filter(RefreshToken.user_id == user.id).delete()
    db.query(SocialAccount).filter(SocialAccount.user_id == user.id).delete()
    db.query(ProductFavorite).filter(ProductFavorite.user_id == user.id).delete()
    db.query(RecentlyViewedProduct).filter(RecentlyViewedProduct.user_id == user.id).delete()
    db.query(UserRegion).filter(UserRegion.user_id == user.id).delete()
    db.query(UserBlock).filter(
        (UserBlock.blocker_id == user.id) | (UserBlock.blocked_id == user.id)
    ).delete(synchronize_session=False)

    user.nickname = f"탈퇴회원{user.id}"
    user.email = f"withdrawn-{user.id}@withdrawn.local"
    user.password_hash = None
    user.phone_number = None
    user.profile_image_url = None
    user.region_id = None
    user.radius_m = None
    db.commit()
    return {"message": "탈퇴가 완료되었습니다."}


def _resolve_region(db: Session, region_id: int | None, dong_code: str | None) -> Region:
    region = None
    if region_id is not None:
        region = db.get(Region, region_id)
    elif dong_code is not None:
        region = db.scalar(select(Region).where(Region.dong_code == dong_code))

    if region is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="지역을 찾을 수 없습니다.")
    return region


def _sync_primary_cache(user: User, user_region: UserRegion) -> None:
    user.region_id = user_region.region_id
    user.radius_m = user_region.radius_m


def _to_user_region_item(user_region: UserRegion, region: Region) -> UserRegionItem:
    return UserRegionItem(
        region_id=region.id,
        dong_name=region.dong_name,
        gu_name=region.gu_name,
        radius_m=user_region.radius_m,
        is_primary=user_region.is_primary,
    )


def _get_owned_user_region(db: Session, user: User, region_id: int) -> UserRegion:
    user_region = (
        db.query(UserRegion).filter(UserRegion.user_id == user.id, UserRegion.region_id == region_id).first()
    )
    if user_region is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="등록되지 않은 동네입니다.")
    return user_region


def _add_user_region(db: Session, user: User, region: Region, radius_m: int, want_primary: bool) -> UserRegionItem:
    existing_count = db.query(UserRegion).filter(UserRegion.user_id == user.id).count()
    if existing_count >= MAX_USER_REGIONS:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"이미 동네를 {MAX_USER_REGIONS}개 등록했어요. 하나를 삭제한 뒤 추가해주세요.",
        )
    if db.query(UserRegion).filter(UserRegion.user_id == user.id, UserRegion.region_id == region.id).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="이미 등록된 동네입니다.")

    # 첫 동네 등록이면 무조건 대표로 — 대표가 하나도 없는 상태를 만들지 않기 위함.
    make_primary = want_primary or existing_count == 0
    if make_primary:
        db.query(UserRegion).filter(UserRegion.user_id == user.id, UserRegion.is_primary.is_(True)).update(
            {UserRegion.is_primary: False}
        )

    user_region = UserRegion(user_id=user.id, region_id=region.id, radius_m=radius_m, is_primary=make_primary)
    db.add(user_region)
    db.flush()
    if make_primary:
        _sync_primary_cache(user, user_region)
    db.commit()
    db.refresh(user_region)
    return _to_user_region_item(user_region, region)


def _set_primary_user_region(db: Session, user: User, user_region: UserRegion, radius_m: int | None) -> UserRegionItem:
    db.query(UserRegion).filter(
        UserRegion.user_id == user.id, UserRegion.is_primary.is_(True), UserRegion.id != user_region.id
    ).update({UserRegion.is_primary: False})
    user_region.is_primary = True
    if radius_m is not None:
        user_region.radius_m = radius_m
    db.flush()
    _sync_primary_cache(user, user_region)
    db.commit()
    db.refresh(user_region)
    region = db.get(Region, user_region.region_id)
    return _to_user_region_item(user_region, region)


def list_user_regions(db: Session, user: User) -> UserRegionListResponse:
    rows = (
        db.query(UserRegion, Region)
        .join(Region, UserRegion.region_id == Region.id)
        .filter(UserRegion.user_id == user.id)
        .order_by(UserRegion.is_primary.desc(), UserRegion.created_at.asc())
        .all()
    )
    return UserRegionListResponse(items=[_to_user_region_item(ur, r) for ur, r in rows])


def add_user_region(db: Session, user: User, payload: UserRegionCreateRequest) -> UserRegionItem:
    region = _resolve_region(db, payload.region_id, payload.dong_code)
    return _add_user_region(db, user, region, payload.radius_m, payload.is_primary)


def set_primary_user_region(
    db: Session, user: User, region_id: int, payload: UserRegionUpdateRequest
) -> UserRegionItem:
    user_region = _get_owned_user_region(db, user, region_id)
    return _set_primary_user_region(db, user, user_region, payload.radius_m)


def remove_user_region(db: Session, user: User, region_id: int) -> None:
    user_region = _get_owned_user_region(db, user, region_id)
    if db.query(UserRegion).filter(UserRegion.user_id == user.id).count() <= 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="최소 1개의 동네는 있어야 해요.")

    was_primary = user_region.is_primary
    db.delete(user_region)
    db.flush()
    if was_primary:
        # 남은 동네가 정확히 1개 남아있는 상태 — 그 동네를 자동으로 대표로 승격.
        remaining = db.query(UserRegion).filter(UserRegion.user_id == user.id).first()
        remaining.is_primary = True
        _sync_primary_cache(user, remaining)
    db.commit()


def update_region(db: Session, user: User, payload: RegionUpdateRequest) -> User:
    """하위 호환용 단일 API — "대표 동네를 이 값으로 바꾼다"로 동작한다.

    이미 등록된 동네면 대표 전환(TASK-11-03), 새 동네면 추가(TASK-11-02)
    로직을 그대로 재사용한다 — docs/issue/11-multi-region.md TASK-11-05.
    """
    region = _resolve_region(db, payload.region_id, payload.dong_code)
    existing = db.query(UserRegion).filter(UserRegion.user_id == user.id, UserRegion.region_id == region.id).first()
    if existing is not None:
        _set_primary_user_region(db, user, existing, payload.radius_m)
    else:
        _add_user_region(db, user, region, payload.radius_m, want_primary=True)
    db.refresh(user)
    return user


def update_profile(db: Session, user: User, payload: ProfileUpdateRequest) -> User:
    # 인증 없이 그냥 수집 — exclude_unset이라 요청에 안 담긴 필드는 건드리지 않는다
    # (예: 사진만 다시 올릴 때 전화번호가 None으로 지워지는 걸 방지).
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="이미 등록된 전화번호입니다.") from exc
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
