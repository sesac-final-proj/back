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
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    detail_category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    trade_place: Mapped[str | None] = mapped_column(String(200), nullable=True)
    desired_price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # 판매자 매너온도/닉네임 — 계산·인증 로직이 아직 없어 크롤링 원본
    # (Transaction.seller_*) 값을 그대로 보여주는 용도. 그래서 스키마상
    # 읽기 전용(Create/UpdateRequest엔 없음).
    seller_nickname: Mapped[str | None] = mapped_column(String(100), nullable=True)
    seller_manner_temp: Mapped[float | None] = mapped_column(Numeric(4, 1), nullable=True)
    # 크롤링 원본 조회수/관심수 스냅샷 — chat_count/favorite_count와 달리 실사용자
    # 반응을 실시간 집계할 방법이 없어(로그인 세션 미연동) 크롤링 시점 값을 그대로 노출.
    view_count: Mapped[int] = mapped_column(Integer, default=0)
    interest_count: Mapped[int] = mapped_column(Integer, default=0)
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
