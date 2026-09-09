"""가격예측 모델(analyzer/ 파이프라인) 산출물을 DB에 적재한 결과.

docs/issue/12-price-prediction-dashboard.md — 재학습 때마다 scripts/seed_price_model_data.py로
analyzer/outputs/*.csv, metrics.json을 통째로 truncate+재적재한다(배치성 스냅샷이라
증분 적재 대신 매번 전량 교체가 더 단순하고 안전).
"""
from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class PriceModelMetric(Base):
    """metrics.json 한 행 = (피처셋, 모델) 조합 하나의 성능 지표.

    lightgbm 쪽에만 있는 부가 필드(best_params, cqr_* 등)는 컬럼을 늘리는 대신
    extra(JSON)에 통째로 넣는다 — 모델마다 필드 구성이 달라서 컬럼화하면 대부분 NULL.
    """

    __tablename__ = "price_model_metrics"

    id: Mapped[int] = mapped_column(primary_key=True)
    feature_set: Mapped[str] = mapped_column(String(30), nullable=False)  # "full" | "no_leak_prone"
    model_key: Mapped[str] = mapped_column(String(30), nullable=False)  # "random_forest" | "lightgbm"
    label: Mapped[str] = mapped_column(String(50), nullable=False)
    rmse: Mapped[float] = mapped_column(Float, nullable=False)
    mae: Mapped[float] = mapped_column(Float, nullable=False)
    mape: Mapped[float] = mapped_column(Float, nullable=False)
    r2: Mapped[float] = mapped_column(Float, nullable=False)
    hit10: Mapped[float] = mapped_column(Float, nullable=False)
    hit20: Mapped[float] = mapped_column(Float, nullable=False)
    extra: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PriceModelListing(Base):
    """viz_전처리완료.csv 한 행 = 학습에 쓰인 매물 하나 — "각 상품별 데이터" 원본.

    가격분포(스웜 플롯)는 이 테이블을 category/detail_type으로 그룹화해서 즉석 계산한다
    (group_median_lookup.csv를 별도 테이블로 안 만든 이유 — 여기서 그대로 재현 가능).
    """

    __tablename__ = "price_model_listings"

    id: Mapped[int] = mapped_column(primary_key=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    detail_type: Mapped[str] = mapped_column(String(50), nullable=False)
    gu: Mapped[str] = mapped_column(String(50), nullable=False)
    condition: Mapped[str] = mapped_column(String(30), nullable=False)  # 상품상태
    status: Mapped[str] = mapped_column(String(30), nullable=False)  # 거래중/거래완료 등
    chat_count: Mapped[int] = mapped_column(Integer, nullable=False)
    interest_count: Mapped[int] = mapped_column(Integer, nullable=False)
    view_count: Mapped[float] = mapped_column(Float, nullable=False)
    manner_temp: Mapped[float] = mapped_column(Float, nullable=False)
    title_length: Mapped[int] = mapped_column(Integer, nullable=False)
    days_since_listed: Mapped[int] = mapped_column(Integer, nullable=False)
    category_detail_median_price: Mapped[float] = mapped_column(Float, nullable=False)
    price: Mapped[int] = mapped_column(Integer, nullable=False)
    price_log: Mapped[float] = mapped_column(Float, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)


class PricePrediction(Base):
    """predictions_sample_{feature_set}.csv 한 행 — 실제가 vs 예측가 산점도용 샘플."""

    __tablename__ = "price_predictions"

    id: Mapped[int] = mapped_column(primary_key=True)
    feature_set: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    detail_type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    actual_price: Mapped[int] = mapped_column(Integer, nullable=False)
    predicted_price: Mapped[int] = mapped_column(Integer, nullable=False)
    error_rate: Mapped[float] = mapped_column(Float, nullable=False)


class PricePlatformComparison(Base):
    """platform_price_comparison.csv 한 행 — 카테고리 x 플랫폼별 가격 통계."""

    __tablename__ = "price_platform_comparisons"

    id: Mapped[int] = mapped_column(primary_key=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String(30), nullable=False)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False)
    mean_price: Mapped[float] = mapped_column(Float, nullable=False)
    median_price: Mapped[float] = mapped_column(Float, nullable=False)
    std_price: Mapped[float] = mapped_column(Float, nullable=False)
    p25_price: Mapped[float] = mapped_column(Float, nullable=False)
    p75_price: Mapped[float] = mapped_column(Float, nullable=False)


class PricePlatformTest(Base):
    """platform_price_tests.csv 한 행 — 플랫폼 두 곳 간 가격 차이 유의성 검정 결과."""

    __tablename__ = "price_platform_tests"

    id: Mapped[int] = mapped_column(primary_key=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    platform_a: Mapped[str] = mapped_column(String(30), nullable=False)
    platform_b: Mapped[str] = mapped_column(String(30), nullable=False)
    median_a: Mapped[float] = mapped_column(Float, nullable=False)
    median_b: Mapped[float] = mapped_column(Float, nullable=False)
    diff_pct: Mapped[float] = mapped_column(Float, nullable=False)
    p_value: Mapped[float] = mapped_column(Float, nullable=False)
    significant: Mapped[bool] = mapped_column(nullable=False)


class PriceCluster(Base):
    """gmm_price_clusters.csv 한 행 — 카테고리 내 가격대(저가/중가/고가 등) GMM 군집."""

    __tablename__ = "price_clusters"

    id: Mapped[int] = mapped_column(primary_key=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    price_band: Mapped[str] = mapped_column(String(30), nullable=False)
    share: Mapped[float] = mapped_column(Float, nullable=False)
    median_price: Mapped[float] = mapped_column(Float, nullable=False)
    range_low: Mapped[float] = mapped_column(Float, nullable=False)
    range_high: Mapped[float] = mapped_column(Float, nullable=False)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False)
