from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    category: Mapped[str] = mapped_column(String(100))
    search_keyword: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    desired_price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    region_id: Mapped[int] = mapped_column(ForeignKey("regions.id"))
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    # DB 컬럼은 plain varchar (Postgres enum 아님) — 값 검증은 schema.py의 Literal에서.
    trade_status: Mapped[str] = mapped_column(String(20), default="SALE")
    trade_type: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
