from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Analysis(Base):
    """가격/거래빈도 분석 요청 1건. 요청 시점 사용자 활동동네를 분석 기준지역으로 굳힌다."""

    __tablename__ = "analyses"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    region_id: Mapped[int] = mapped_column(ForeignKey("regions.id"))
    requested_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    # DB 컬럼은 plain varchar — 값 검증은 서비스 레이어에서.
    status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AnalysisResult(Base):
    """Analysis 1건당 산출 결과 1건 (analysis_id UNIQUE) — 가격범위/거래빈도/근거를 한 번에 계산해 캐싱."""

    __tablename__ = "analysis_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("analyses.id"), unique=True)
    price_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    frequency_grade: Mapped[str] = mapped_column(String(10))
    sample_count: Mapped[int] = mapped_column(Integer, default=0)
    # avg_chat_count/avg_interest_count 등 근거 통계 + 근거 샘플(상위 N건)을 함께 담는다.
    # 736eeb896604(staging existing-baseline 마이그레이션)가 이미 plain JSON으로
    # 만들어놔서 맞춘다 — JSONB 전용 연산자(포함검색 등)를 쓰지 않으니 상관없고,
    # SQLite 기반 단위테스트(예: test_auth_nickname.py)와도 호환된다.
    evidence_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
