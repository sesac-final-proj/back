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


@router.get("/points", response_model=schema.PointBalanceResponse)
def get_points(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return service.get_point_balance(db, user, page, size)
