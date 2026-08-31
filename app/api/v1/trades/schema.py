from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel


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
