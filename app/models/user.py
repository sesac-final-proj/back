import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class UserRole(str, enum.Enum):
    USER = "user"
    ADMIN = "admin"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    nickname: Mapped[str] = mapped_column(String(50))
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role"), default=UserRole.USER
    )

    # MVP는 사용자당 활동동네 1개 + 거래반경만 지원 (Req.2, SCR.2 입력 화면 기준
    # 단일 값). 여러 활동동네 지원은 PRD상 가능성만 언급돼 있고 화면/요구사항에
    # 없어 YAGNI로 단일 FK 선택 — 다건 필요해지면 UserRegion 매핑 테이블로 분리.
    region_id: Mapped[int | None] = mapped_column(ForeignKey("regions.id"), nullable=True)
    radius_m: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
