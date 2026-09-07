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
    nickname_set: bool
    phone_number: str | None
    profile_image_url: str | None
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


class UserRegionItem(BaseModel):
    region_id: int
    dong_name: str
    gu_name: str
    radius_m: int
    is_primary: bool


class UserRegionListResponse(BaseModel):
    items: list[UserRegionItem]


class UserRegionCreateRequest(BaseModel):
    region_id: int | None = None
    dong_code: str | None = None
    radius_m: int
    is_primary: bool = False

    @model_validator(mode="after")
    def check_region_identifier(self):
        if self.region_id is None and self.dong_code is None:
            raise ValueError("region_id 또는 dong_code 중 하나는 필요합니다.")
        return self


class UserRegionUpdateRequest(BaseModel):
    # 지금은 "대표 동네로 전환"용으로만 쓴다 — false로 내리는(대표 해제) 용도는
    # 없다(다른 동네를 대표로 지정하는 방식으로만 전환 가능).
    is_primary: bool = True
    radius_m: int | None = None

    @model_validator(mode="after")
    def check_is_primary(self):
        if not self.is_primary:
            raise ValueError("is_primary=false는 지원하지 않습니다. 다른 동네를 대표로 지정해주세요.")
        return self


class ProfileUpdateRequest(BaseModel):
    # 인증 없이 그냥 수집만 한다 — 010xxxxxxxx 형태로, 하이픈/공백은 프론트에서
    # 벗겨서 보내도록. 둘 다 optional이라 값이 있는 필드만 부분 갱신된다.
    phone_number: str | None = None
    profile_image_url: str | None = None
