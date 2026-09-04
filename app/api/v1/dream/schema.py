from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.core.pagination import Page


class PointTransactionItem(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    amount: int
    source: Literal["general_payment", "trade"]
    related_id: int | None
    created_at: datetime


class PointBalanceResponse(BaseModel):
    balance: int
    transactions: Page[PointTransactionItem]


class FacilityItem(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    name: str
    district: str
    facility_type: str
    address: str
    phone: str | None = None
    lat: float | None = None
    lng: float | None = None


class FacilityListResponse(BaseModel):
    items: list[FacilityItem]
    total: int
    geocoded_count: int
    source: Literal["seoul_open_data", "seoul_sample"]
    notice: str | None = None


class DonationSettingRequest(BaseModel):
    donation_rate: int = Field(ge=0, le=100)
    facility_id: int


class DonationSettingResponse(BaseModel):
    donation_rate: int
    facility_id: int


class DonationItem(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    facility_name: str
    amount: int
    created_at: datetime


class DonationListResponse(BaseModel):
    total_amount: int
    items: Page[DonationItem]
