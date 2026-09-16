from datetime import date

from pydantic import BaseModel


class ShareResultItem(BaseModel):
    region_name: str
    total_donation: int
    total_spend: int


class MerchantSpendItem(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    merchant_name: str
    region_name: str
    amount: int
    spent_at: date
    description: str | None


class CirculationRateResponse(BaseModel):
    region_name: str
    total_donation: int
    total_spend: int
    rate_percent: float | None
