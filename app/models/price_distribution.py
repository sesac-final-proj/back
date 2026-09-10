"""당근마켓 크롤링 분석(crawling_Data 세션) 산출물을 DB에 적재한 결과 — 어드민 전용.

price_model.py(팀원의 가격예측 ML 모델)과는 별개 기능이다. 이쪽은 유저 요청 단위로
계산되는 Analysis/AnalysisResult(단일 지역 기준)와도 다르게, "상품 x 구" 전체를
한 번에 모아 어드민이 지역별로 비교해보는 대시보드용 스냅샷이다.

scripts/seed_price_distribution_data.py 로 daangn_통합_*.csv 를 읽어 재적재한다
(price_model과 동일하게 배치 스냅샷 — 전량 truncate 후 재적재, 멱등).
"""
from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class PriceCategorySummary(Base):
    """카테고리(상품) 하나의 전체 요약 — 어드민 상세화면 상단 카드 4개(표준편차/가격추세/
    거래빈도등급/표본수)에 대응. 적정가격 range는 팀원 모델(PricePrediction) 담당이라
    여기서는 다루지 않는다."""

    __tablename__ = "price_category_summaries"

    id: Mapped[int] = mapped_column(primary_key=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False)
    median_price: Mapped[float] = mapped_column(Float, nullable=False)
    std_price: Mapped[float] = mapped_column(Float, nullable=False)
    cv_price: Mapped[float] = mapped_column(Float, nullable=False)  # 변동계수(%) = std/mean*100
    price_trend_pct: Mapped[float | None] = mapped_column(Float, nullable=True)  # 최근 180일 중앙값 변화율(%), 표본부족 시 NULL
    frequency_grade: Mapped[str] = mapped_column(String(10), nullable=False)  # S/A/B/C
    listings_per_month: Mapped[float] = mapped_column(Float, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PriceRegionStat(Base):
    """카테고리 x 구 하나 — 지역별 비교 표(중앙값가격/완료율/매너온도) 한 행.

    completion_rate는 있는 그대로 노출한다 — 송파구는 크롤링 상태필드 결함으로
    실제보다 낮게 나올 수 있다는 걸 알고 쓰는 값(별도 신뢰도 플래그 없음)."""

    __tablename__ = "price_region_stats"

    id: Mapped[int] = mapped_column(primary_key=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    gu: Mapped[str] = mapped_column(String(30), nullable=False)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False)
    median_price: Mapped[float] = mapped_column(Float, nullable=False)
    completion_rate: Mapped[float] = mapped_column(Float, nullable=False)  # %
    avg_manner_temp: Mapped[float] = mapped_column(Float, nullable=False)


class PriceDetailTypeStat(Base):
    """카테고리 x 세부유형(모델) x 구 하나 — 다이슨 V6/V8/V10처럼 모델별로 쪼갠 가격
    변동성을 지역별로도 나눈 것. gu='전체'는 3개 구를 합친 기준값(구분 없이 볼 때 사용).

    세부유형 필드가 없는 상품(미닉스/브레짜)은 행이 아예 없을 수 있다 — 프론트에서
    빈 리스트면 "모델 구분 없음"으로 안내. 표본이 너무 적은 (세부유형, 구) 조합은
    seed 단계에서 아예 제외한다(임계값은 seed 스크립트 참고)."""

    __tablename__ = "price_detail_type_stats"

    id: Mapped[int] = mapped_column(primary_key=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    detail_type: Mapped[str] = mapped_column(String(50), nullable=False)
    gu: Mapped[str] = mapped_column(String(30), nullable=False, default="전체")
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False)
    median_price: Mapped[float] = mapped_column(Float, nullable=False)
    cv_price: Mapped[float] = mapped_column(Float, nullable=False)


class PriceListingSample(Base):
    """카테고리 x 구 하나에서 뽑은 개별 매물 가격 표본(구별 최대 600건) — 스웜 플롯
    렌더링용(price_model.py의 PriceModelListing 기반 스웜 플롯과 같은 패턴). 집계치
    (PriceRegionStat)만으로는 점 하나하나를 못 그려서 별도로 원본 단위 표본을 둔다.
    상위 3% 가격 이상치는 시각화 왜곡 방지를 위해 표본 추출 전에 제외."""

    __tablename__ = "price_listing_samples"

    id: Mapped[int] = mapped_column(primary_key=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    gu: Mapped[str] = mapped_column(String(30), nullable=False)
    price: Mapped[int] = mapped_column(Integer, nullable=False)


class PriceDongStat(Base):
    """카테고리 x 구 x 동 하나 — 동네 시세지도(dong_map) 한 타일에 대응."""

    __tablename__ = "price_dong_stats"

    id: Mapped[int] = mapped_column(primary_key=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    gu: Mapped[str] = mapped_column(String(30), nullable=False)
    dong: Mapped[str] = mapped_column(String(30), nullable=False)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False)
    median_price: Mapped[float] = mapped_column(Float, nullable=False)
    within_pct: Mapped[float] = mapped_column(Float, nullable=False)  # 카테고리 Q1~Q3 안에 드는 비중
    below_pct: Mapped[float] = mapped_column(Float, nullable=False)
    above_pct: Mapped[float] = mapped_column(Float, nullable=False)
    dev_pct: Mapped[float] = mapped_column(Float, nullable=False)  # 카테고리 전체 중앙값 대비 이 동의 편차(%)
