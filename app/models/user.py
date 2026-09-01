import enum
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

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
    nickname: Mapped[str] = mapped_column(String(50))
    # 실제 DB 컬럼은 Postgres 네이티브 enum이 아니라 plain varchar + CHECK
    # (role IN ('user','admin'), 소문자) — SQLAlchemy Enum을 쓰면 (사용 안 하는)
    # 동명의 user_role enum 타입으로 캐스팅을 시도해서 깨진다. String으로 저장하고
    # 값 검증은 UserRole(str, Enum) 쪽에서 담당.
    role: Mapped[UserRole] = mapped_column(String(20), default=UserRole.USER)

    # 활동동네는 단일 FK (docs/ERD.md 0절) — 다건 필요해지면 UserRegion 매핑 테이블로 분리.
    region_id: Mapped[int | None] = mapped_column(ForeignKey("regions.id"), nullable=True)
    radius_m: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
