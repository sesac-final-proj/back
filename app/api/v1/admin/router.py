from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.v1.admin import schema, service
from app.core.db import get_db
from app.core.deps import require_admin
from app.models.user import User


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


@router.get("/price-model/detail-type-counts", response_model=schema.DetailTypeCountsResponse)
def price_model_detail_type_counts(db: Session = Depends(get_db)):
    return service.get_detail_type_counts(db)


@router.get("/price-model/shap-summary")
def price_model_shap_summary(feature_set: Literal["full", "no_leak_prone"] = "full"):
    path = service.get_shap_summary_path(feature_set)
    if path is None:
        raise HTTPException(status_code=404, detail="SHAP 요약 이미지가 없습니다.")
    return FileResponse(path, media_type="image/png")


@router.get("/notices", response_model=schema.NoticeListResponse)
def notices(
    q: str | None = None,
    service_name: str | None = Query(default=None, alias="service"),
    notice_status: str | None = Query(default=None, alias="status"),
    delete_status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    return service.list_notices(db, q=q, service=service_name, status=notice_status, delete_status=delete_status, page=page, size=size)


@router.post("/notices", response_model=schema.NoticeListItem, status_code=status.HTTP_201_CREATED)
def create_notice(
    payload: schema.NoticeCreateRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    return service.create_notice(db, admin, payload)


@router.patch("/notices/order", response_model=schema.NoticeListResponse)
def reorder_notices(
    payload: schema.NoticeOrderRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    return service.reorder_notices(db, admin, payload)


@router.patch("/notices/{notice_id}", response_model=schema.NoticeListItem)
def update_notice(
    notice_id: int,
    payload: schema.NoticeUpdateRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    try:
        return service.update_notice(db, admin, notice_id, payload)
    except ValueError as error:
        raise HTTPException(status_code=404, detail="공지를 찾을 수 없습니다.") from error


@router.delete("/notices/{notice_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_notice(
    notice_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    try:
        service.soft_delete_notice(db, admin, notice_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail="공지를 찾을 수 없습니다.") from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/notices/{notice_id}/duplicate", response_model=schema.NoticeListItem, status_code=status.HTTP_201_CREATED)
def duplicate_notice(
    notice_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    try:
        return service.duplicate_notice(db, admin, notice_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail="공지를 찾을 수 없습니다.") from error


@router.post("/notices/{notice_id}/alerts", response_model=schema.AlertCreatedResponse)
def create_notice_alerts(notice_id: int, db: Session = Depends(get_db)):
    try:
        return service.create_notice_alerts(db, notice_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail="공지를 찾을 수 없습니다.") from error
