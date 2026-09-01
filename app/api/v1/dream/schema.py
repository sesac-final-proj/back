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

    id: int
    name: str
    region_name: str
    description: str | None


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
