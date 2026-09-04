from urllib.parse import urlencode

from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.api.v1.auth import service
from app.api.v1.auth.schema import (
    LoginRequest,
    LogoutRequest,
    MeResponse,
    MeSummaryResponse,
    PasswordChangeRequest,
    PhoneSendCodeRequest,
    PhoneVerifyRequest,
    ProfileImageUpdateRequest,
    RefreshRequest,
    RefreshResponse,
    RegionUpdateRequest,
    SignupRequest,
    SignupResponse,
    TokenResponse,
)
from app.core.config import settings
from app.core.db import get_db
from app.core.deps import get_current_user, require_admin
from app.models.user import User

router = APIRouter(prefix="/api/v1/auth", tags=["회원관리"])
legacy_router = APIRouter(tags=["회원관리"])


@router.post("/signup", response_model=SignupResponse)
def signup(payload: SignupRequest, db: Session = Depends(get_db)):
    return service.signup(db, payload)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    return service.login(db, payload)


@router.post("/logout")
def logout(payload: LogoutRequest, db: Session = Depends(get_db)):
    return service.logout(db, payload.refresh_token)


@router.post("/refresh", response_model=RefreshResponse)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    return service.refresh(db, payload.refresh_token)


@router.get("/me", response_model=MeResponse)
def me(user: User = Depends(get_current_user)):
    return user


@router.put("/me/region", response_model=MeResponse)
def update_region(
    payload: RegionUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return service.update_region(db, user, payload)


@router.get("/me/summary", response_model=MeSummaryResponse)
def me_summary(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return service.get_me_summary(db, user)


@router.put("/me/profile-image", response_model=MeResponse)
def update_profile_image(
    payload: ProfileImageUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return service.update_profile_image(db, user, payload.profile_image_url)


@router.post("/phone/send-code", status_code=204)
def send_phone_code(payload: PhoneSendCodeRequest, user: User = Depends(get_current_user)):
    service.send_phone_code(payload.phone_number)


@router.post("/phone/verify", response_model=MeResponse)
def verify_phone_code(
    payload: PhoneVerifyRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return service.verify_phone_code(db, user, payload)


@router.post("/admin/login", response_model=TokenResponse)
def admin_login(payload: LoginRequest, db: Session = Depends(get_db)):
    return service.admin_login(db, payload)


@router.post("/admin/refresh", response_model=RefreshResponse)
def admin_refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    return service.refresh(db, payload.refresh_token, required_role="admin")


@router.post("/admin/logout")
def admin_logout(payload: LogoutRequest, db: Session = Depends(get_db)):
    return service.logout(db, payload.refresh_token)


@router.get("/admin/me", response_model=MeResponse)
def admin_me(user: User = Depends(require_admin)):
    return user


@router.post("/admin/password")
def change_admin_password(
    payload: PasswordChangeRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return service.change_admin_password(
        db,
        admin,
        current_password=payload.current_password,
        new_password=payload.new_password,
    )


@router.get("/login/{provider}")
def social_login_url(provider: str):
    return service.oauth_login_url(provider)


@router.get("/oauth/{provider}/callback")
def social_callback(
    provider: str,
    code: str,
    state: str | None = None,
    db: Session = Depends(get_db),
):
    # 카카오/네이버 콘솔에 등록된 Redirect URI가 이 경로라 브라우저가 직접
    # 도착한다 — JSON을 돌려주면 사용자가 빈 JSON 화면에 남으므로, 토큰을
    # 쿼리스트링에 담아 프론트 콜백 페이지로 리다이렉트한다.
    tokens = service.oauth_callback(db, provider, code, state)
    query = urlencode(tokens)
    return RedirectResponse(f"{settings.FRONTEND_ORIGIN}/auth/callback?{query}")


@legacy_router.get("/auth/login/{provider}")
def legacy_social_login_url(provider: str):
    return service.oauth_login_url(provider)


@legacy_router.get("/auth/callback/{provider}")
def legacy_social_callback(
    provider: str,
    code: str,
    state: str | None = None,
    db: Session = Depends(get_db),
):
    # 카카오/네이버 콘솔에 등록된 Redirect URI가 이 경로라 브라우저가 직접
    # 도착한다 — JSON을 돌려주면 사용자가 빈 JSON 화면에 남으므로, 토큰을
    # 쿼리스트링에 담아 프론트 콜백 페이지로 리다이렉트한다.
    tokens = service.oauth_callback(db, provider, code, state)
    query = urlencode(tokens)
    return RedirectResponse(f"{settings.FRONTEND_ORIGIN}/auth/callback?{query}")
