from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.v1.local import schema, service, transit_service
from app.core.db import get_db
from app.local_info.congestion_service import CongestionUnavailableError, get_congestion_zones

router = APIRouter(prefix="/api/v1/local", tags=["갖가지"])


@router.get("/danger-signals", response_model=schema.DangerSignalListResponse)
def list_danger_signals(
    sigungu: str | None = None,
    q: str | None = None,
    limit: int = Query(default=80, ge=1, le=200),
    db: Session = Depends(get_db),
):
    return service.list_danger_signals(db, sigungu=sigungu, q=q, limit=limit)


@router.get("/transit", response_model=transit_service.TransitResponse)
def list_transit(
    kind: transit_service.TransitKind,
    sw_lat: float = Query(ge=-90, le=90),
    sw_lng: float = Query(ge=-180, le=180),
    ne_lat: float = Query(ge=-90, le=90),
    ne_lng: float = Query(ge=-180, le=180),
    limit: int = Query(default=120, ge=1, le=200),
):
    return transit_service.list_transit(kind, sw_lat, sw_lng, ne_lat, ne_lng, limit)


@router.get("/congestion-zones")
def list_congestion_zones(
    sw_lat: float | None = None,
    sw_lng: float | None = None,
    ne_lat: float | None = None,
    ne_lng: float | None = None,
    neighborhood: str | None = None,
    limit: int = Query(default=30, ge=1, le=100),
):
    try:
        return get_congestion_zones(sw_lat, sw_lng, ne_lat, ne_lng, neighborhood, limit)
    except ValueError as error:
        raise HTTPException(status_code=400, detail="지도 범위를 확인해 주세요.") from error
    except CongestionUnavailableError as error:
        raise HTTPException(status_code=503, detail="서울시 혼잡도 정보를 불러오지 못했어요.") from error
