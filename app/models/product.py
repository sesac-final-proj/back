from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    category: Mapped[str] = mapped_column(String(100))
    detail_category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    search_keyword: Mapped[str | None] = mapped_column(String(100), nullable=True)
    desired_price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    region_id: Mapped[int] = mapped_column(ForeignKey("regions.id"))
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    # DB 컬럼은 plain varchar (Postgres enum 아님) — 값 검증은 schema.py의 Literal에서.
    trade_status: Mapped[str] = mapped_column(String(20), default="SALE")
    trade_type: Mapped[str] = mapped_column(String(20))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    trade_place: Mapped[str | None] = mapped_column(String(200), nullable=True)
    seller_nickname: Mapped[str | None] = mapped_column(String(100), nullable=True)
    seller_manner_temp: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    view_count: Mapped[int] = mapped_column(Integer, default=0)
    interest_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
