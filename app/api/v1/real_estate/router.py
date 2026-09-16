from datetime import date
from typing import Literal

from fastapi import APIRouter, Query

from app.api.v1.real_estate import schema, service

router = APIRouter(prefix="/api/real-estate", tags=["부동산"])


@router.get("/rent", response_model=schema.RentTransactionListResponse)
def list_rent_transactions(
    district: str = Query(default="송파구", min_length=2, max_length=12),
    dong: str | None = Query(default=None, max_length=20),
    q: str | None = Query(default=None, max_length=50),
    rent_type: Literal["monthly", "jeonse", "all"] = "monthly",
    house_type: Literal["apartment", "one_room", "two_plus", "officetel", "house", "all"] = "all",
    deposit_max: int | None = Query(default=None, ge=0),
    monthly_rent_max: int | None = Query(default=None, ge=0),
    year: int = Query(default_factory=lambda: date.today().year, ge=2023, le=2100),
    south: float | None = Query(default=None, ge=33.0, le=39.0),
    north: float | None = Query(default=None, ge=33.0, le=39.0),
    west: float | None = Query(default=None, ge=124.0, le=132.0),
    east: float | None = Query(default=None, ge=124.0, le=132.0),
    limit: int = Query(default=160, ge=1, le=300),
):
    return service.list_rent_transactions(
        district=district,
        dong=dong,
        q=q,
        rent_type=rent_type,
        house_type=house_type,
        deposit_max=deposit_max,
        monthly_rent_max=monthly_rent_max,
        year=year,
        south=south,
        north=north,
        west=west,
        east=east,
        limit=limit,
    )
