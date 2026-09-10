from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.v1.admin import schema, service
from app.core.db import get_db
from app.core.deps import require_admin


router = APIRouter(
    prefix="/api/v1/admin",
    tags=["어드민"],
    dependencies=[Depends(require_admin)],
)


@router.get("/data-status", response_model=schema.DataStatusResponse)
def data_status(
    db: Session = Depends(get_db),
):
    return service.get_data_status(db)


@router.get("/dashboard/overview", response_model=schema.DashboardOverview)
def dashboard_overview(range: Literal["14d"] = "14d", db: Session = Depends(get_db)):
    return service.get_dashboard_overview(db)


@router.get("/audience-insights", response_model=schema.AudienceInsightsResponse)
def audience_insights():
    return service.get_audience_insights()


@router.get("/dream-status", response_model=schema.DreamStatusResponse)
def dream_status():
    return service.get_dream_status()


# --------------------------------------------------------------------------
# 가격예측 모델 대시보드 (docs/issue/12-price-prediction-dashboard.md)
# --------------------------------------------------------------------------


@router.get("/price-model/metrics", response_model=schema.PriceModelMetricsResponse)
def price_model_metrics(db: Session = Depends(get_db)):
    return service.get_price_model_metrics(db)


@router.get("/price-model/listings", response_model=schema.PriceModelListingListResponse)
def price_model_listings(
    category: str | None = None,
    detail_type: str | None = None,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
):
    return service.list_price_model_listings(db, category, detail_type, page, size)


@router.get("/price-model/price-distribution", response_model=schema.PriceDistributionResponse)
def price_model_price_distribution(
    category: str | None = None,
    sample: int = Query(default=2000, ge=1, le=10000),
    db: Session = Depends(get_db),
):
    return service.get_price_distribution(db, category, sample)


@router.get("/price-model/charts", response_model=schema.PriceModelChartsResponse)
def price_model_charts(db: Session = Depends(get_db)):
    return service.get_price_model_charts(db)


# --------------------------------------------------------------------------
# 가격 지역별 비교 대시보드 (crawling_Data 세션 산출물, price_model과 별개 기능)
# --------------------------------------------------------------------------


@router.get("/price-comparison/overview", response_model=schema.PriceComparisonOverviewResponse)
def price_comparison_overview(db: Session = Depends(get_db)):
    return service.get_price_comparison_overview(db)


@router.get("/price-comparison/samples", response_model=schema.PriceComparisonSamplesResponse)
def price_comparison_samples(
    category: str,
    gu: str | None = None,
    sample: int = Query(default=2000, ge=1, le=10000),
    db: Session = Depends(get_db),
):
    return service.get_price_comparison_samples(db, category, gu, sample)
