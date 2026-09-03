from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

from app.core.pagination import Page

TradeStatus = Literal["SALE", "RESERVED", "SOLD"]
TradeType = Literal["SALE", "FREE"]


class ProductCreateRequest(BaseModel):
    title: str
    category: str
    desired_price: int | None = None
    trade_type: TradeType = "SALE"
    description: str | None = None


class ProductCreated(BaseModel):
    id: int


class ProductListItem(BaseModel):
    """carrot/mock_contract.py의 ProductListItem과 필드명을 맞춘다.

    단, id는 mock의 문자열 placeholder("p1")가 아니라 실제 DB PK(int)를
    쓰고, created_at도 mock의 사전 포맷 문자열("17시간 전") 대신 실제
    datetime을 반환한다 — 상대시간 포맷팅은 프론트 책임으로 둔다.
    """

    model_config = {"from_attributes": True}

    id: int
    title: str
    neighborhood_name: str
    created_at: datetime
    price: int | None
    trade_status: TradeStatus
    trade_type: TradeType
    chat_count: int
    favorite_count: int


ProductListResponse = Page[ProductListItem]


class ProductDetailResponse(ProductListItem):
    category: str
    search_keyword: str | None
    description: str | None
    seller_manner_temp: float | None


class ProductStatusUpdateRequest(BaseModel):
    trade_status: TradeStatus


class ProductUpdateRequest(BaseModel):
    title: str | None = None
    category: str | None = None
    desired_price: int | None = None
    search_keyword: str | None = None
    description: str | None = None


class FavoriteToggleResponse(BaseModel):
    favorited: bool
    favorite_count: int


ProductFavoritesResponse = Page[ProductListItem]


class AnalysisRequest(BaseModel):
    product_title: str
    category: str
    desired_price: int | None = None


class AnalysisCreated(BaseModel):
    analysis_id: int


class SimilarTransactionItem(BaseModel):
    product_title: str
    price: int | None
    listed_at: date
    region_name: str | None


class PriceRangeResponse(BaseModel):
    status: Literal["ok", "insufficient_data"]
    price_min: int | None = None
    price_max: int | None = None
    sample_count: int


FrequencyGrade = Literal["많음", "보통", "낮음", "산정불가"]


class FrequencyResponse(BaseModel):
    frequency_grade: FrequencyGrade
    sample_count: int


class EvidenceResponse(BaseModel):
    sample_count: int
    avg_chat_count: float
    avg_interest_count: float
    sample_transactions: list[SimilarTransactionItem]
    computed_at: datetime
