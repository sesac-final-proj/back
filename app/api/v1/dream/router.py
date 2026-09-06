from fastapi import APIRouter, Query

from app.api.v1.dream import schema, service

router = APIRouter(prefix="/api/v1/dream", tags=["꿈가지"])


@router.get("/facilities", response_model=schema.FacilityListResponse)
def list_facilities(
    district: str = Query(default="송파구", min_length=2, max_length=12),
    limit: int = Query(default=50, ge=1, le=100),
):
    return service.list_facilities(district, limit)
