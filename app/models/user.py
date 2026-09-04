import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class UserRole(str, enum.Enum):
    USER = "user"
    ADMIN = "admin"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    # 소셜 로그인 전용 유저는 비밀번호가 없다 (docs/ERD.md 0절) — nullable.
    # 이메일 회원가입 유저는 앱 레벨에서 필수로 검증한다.
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    nickname: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    # 소셜 로그인 직후엔 임시 닉네임("사용자1234")이 자동으로 들어가 있어서, nickname이
    # non-null이란 사실만으론 "본인이 실제로 골랐는지"를 구분 못 한다 — 온보딩 단계
    # 판단(닉네임 설정 화면을 또 보여줘야 하는지)에 별도 플래그가 필요.
    nickname_set: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    phone_number: Mapped[str | None] = mapped_column(String(20), unique=True, nullable=True)
    phone_verified: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    profile_image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # 실제 DB 컬럼은 Postgres 네이티브 enum이 아니라 plain varchar + CHECK
    # (role IN ('user','admin'), 소문자) — SQLAlchemy Enum을 쓰면 (사용 안 하는)
    # 동명의 user_role enum 타입으로 캐스팅을 시도해서 깨진다. String으로 저장하고
    # 값 검증은 UserRole(str, Enum) 쪽에서 담당.
    role: Mapped[UserRole] = mapped_column(String(20), default=UserRole.USER)

    # 활동동네는 단일 FK (docs/ERD.md 0절) — 다건 필요해지면 UserRegion 매핑 테이블로 분리.
    region_id: Mapped[int | None] = mapped_column(ForeignKey("regions.id"), nullable=True)
    radius_m: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    region = relationship("Region")


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    token: Mapped[str] = mapped_column(String(512), unique=True, nullable=False)
    revoked: Mapped[bool] = mapped_column(default=False, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SocialProvider(str, enum.Enum):
    KAKAO = "kakao"
    NAVER = "naver"


class SocialAccount(Base):
    __tablename__ = "social_accounts"
    __table_args__ = (
        UniqueConstraint("provider", "provider_user_id", name="social_accounts_provider_provider_user_id_key"),
        UniqueConstraint("user_id", "provider", name="social_accounts_user_id_provider_key"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    provider_user_id: Mapped[str] = mapped_column(String(100), nullable=False)
    access_token: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    refresh_token: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    connected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
