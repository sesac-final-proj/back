from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class UserRegion(Base):
    """유저가 등록한 활동동네(최대 2개). User.region_id/radius_m은 이 중
    is_primary=true인 행의 캐시로 유지된다 — docs/issue/11-multi-region.md."""

    __tablename__ = "user_regions"
    __table_args__ = (UniqueConstraint("user_id", "region_id", name="user_regions_user_id_region_id_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    region_id: Mapped[int] = mapped_column(ForeignKey("regions.id"), nullable=False)
    radius_m: Mapped[int] = mapped_column(Integer, nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
