from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Transaction(Base):
    """당근 크롤링 원천 거래 데이터. CSV → 컬럼 매핑은 docs/ERD.md 4절 참고."""

    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_title: Mapped[str] = mapped_column(String(200))
    search_keyword: Mapped[str | None] = mapped_column(String(100), nullable=True)
    category: Mapped[str] = mapped_column(String(50))
    detail_category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # 매칭 실패(원본 CSV 지역값 공백 등) 시 NULL 허용 — docs/ERD.md 0절.
    region_id: Mapped[int | None] = mapped_column(ForeignKey("regions.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(30))
    trade_place: Mapped[str | None] = mapped_column(String(200), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    seller_nickname: Mapped[str | None] = mapped_column(String(100), nullable=True)
    seller_manner_temp: Mapped[float | None] = mapped_column(Numeric(4, 1), nullable=True)
    chat_count: Mapped[int] = mapped_column(Integer, default=0)
    interest_count: Mapped[int] = mapped_column(Integer, default=0)
    view_count: Mapped[int] = mapped_column(Integer, default=0)
    listed_at: Mapped[date] = mapped_column(Date)
    traded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
