from datetime import datetime

from pydantic import BaseModel, EmailStr, model_validator

from app.models.user import UserRole


class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    nickname: str


class SignupResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    email: str
    nickname: str
    created_at: datetime


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class LogoutRequest(BaseModel):
    refresh_token: str


class RefreshRequest(BaseModel):
    refresh_token: str


class RefreshResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str


class RegionSummary(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    dong_name: str
    gu_name: str


class MeResponse(BaseModel):
    id: int
    email: str
    nickname: str
    role: UserRole
    region: RegionSummary | None
    radius_m: int | None


class RegionUpdateRequest(BaseModel):
    region_id: int | None = None
    dong_code: str | None = None
    radius_m: int

    @model_validator(mode="after")
    def check_region_identifier(self):
        if self.region_id is None and self.dong_code is None:
            raise ValueError("region_id 또는 dong_code 중 하나는 필요합니다.")
        return self


class MeSummaryResponse(BaseModel):
    region: RegionSummary | None
    trade_count: int
    point_balance: int
