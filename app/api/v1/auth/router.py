from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.auth import service
from app.api.v1.auth.schema import (
    LoginRequest,
    LogoutRequest,
    MeResponse,
    PasswordChangeRequest,
    RefreshRequest,
    RefreshResponse,
    RegionUpdateRequest,
    SignupRequest,
    SignupResponse,
    TokenResponse,
)
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
    tokens = service.refresh(db, payload.refresh_token)
    return {"access_token": tokens["access_token"], "token_type": tokens["token_type"]}


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


@router.post("/admin/login", response_model=TokenResponse)
def admin_login(payload: LoginRequest, db: Session = Depends(get_db)):
    return service.admin_login(db, payload)


@router.post("/admin/refresh", response_model=RefreshResponse)
def admin_refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    tokens = service.refresh(db, payload.refresh_token, required_role="admin")
    return {"access_token": tokens["access_token"], "token_type": tokens["token_type"]}


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


@router.get("/oauth/{provider}/callback", response_model=TokenResponse)
def social_callback(
    provider: str,
    code: str,
    state: str | None = None,
    db: Session = Depends(get_db),
):
    return service.oauth_callback(db, provider, code, state)


@legacy_router.get("/auth/login/{provider}")
def legacy_social_login_url(provider: str):
    return service.oauth_login_url(provider)


@legacy_router.get("/auth/callback/{provider}", response_model=TokenResponse)
def legacy_social_callback(
    provider: str,
    code: str,
    state: str | None = None,
    db: Session = Depends(get_db),
):
    return service.oauth_callback(db, provider, code, state)
