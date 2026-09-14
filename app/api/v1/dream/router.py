from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.v1.dream import schema, service
from app.core.db import get_db
from app.core.deps import get_current_user
from app.models.user import User

router = APIRouter(prefix="/api/v1/dream", tags=["꿈가지"])


@router.get("/facilities", response_model=schema.FacilityListResponse)
def list_facilities(
    district: str = Query(default="송파구", min_length=2, max_length=12),
    limit: int = Query(default=50, ge=1, le=100),
):
    return service.list_facilities(district, limit)


@router.get("/district-summary", response_model=schema.DistrictDonationSummaryResponse)
def get_district_summary(
    district: str = Query(min_length=2, max_length=12),
    db: Session = Depends(get_db),
):
    # 로그인 없이도 동네 화면에서 보여주는 집계라 인증 불필요.
    return service.get_district_donation_summary(db, district)


@router.get("/points", response_model=schema.PointBalanceResponse)
def get_points(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return service.get_point_balance(db, user, page, size)
