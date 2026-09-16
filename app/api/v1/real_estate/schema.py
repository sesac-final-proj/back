from typing import Literal

from pydantic import BaseModel

RentType = Literal["monthly", "jeonse"]
HouseType = Literal["apartment", "one_room", "two_plus", "officetel", "house"]


class RentTransaction(BaseModel):
    id: str
    district: str
    dong: str
    building_name: str | None = None
    address: str
    rent_type: RentType
    deposit: int
    monthly_rent: int
    area_m2: float
    floor: int | None = None
    contract_date: str
    house_type: HouseType
    house_type_label: str
    build_year: int | None = None
    lat: float | None = None
    lng: float | None = None


class RentTransactionListResponse(BaseModel):
    items: list[RentTransaction]
    total: int
    source: Literal["seoul_open_data", "seoul_sample"]
    geocoded_count: int
    notice: str | None = None
