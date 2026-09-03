from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, func
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
    # 판매자 매너온도 — 계산 로직이 아직 없어 크롤링 원본(Transaction.seller_manner_temp)
    # 값을 그대로 보여주는 용도. 그래서 스키마상 읽기 전용(Create/UpdateRequest엔 없음).
    seller_manner_temp: Mapped[float | None] = mapped_column(Numeric(4, 1), nullable=True)
    region_id: Mapped[int] = mapped_column(ForeignKey("regions.id"))
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    # DB 컬럼은 plain varchar (Postgres enum 아님) — 값 검증은 schema.py의 Literal에서.
    trade_status: Mapped[str] = mapped_column(String(20), default="SALE")
    trade_type: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
