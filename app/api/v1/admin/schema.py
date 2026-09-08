from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

from app.core.pagination import Page


class RegionDataCount(BaseModel):
    region_name: str
    normal_count: int = 0
    error_count: int = 0
    error_rate: float = 0.0
    transaction_count: int = 0


class CategoryDataCount(BaseModel):
    category: str
    normal_count: int = 0
    error_count: int = 0
    error_rate: float = 0.0
    transaction_count: int = 0


class RecentTransactionItem(BaseModel):
    id: int
    product_title: str
    category: str
    price: int | None
    region_name: str | None
    status: str
    listed_at: date
    collected_at: datetime


class CollectionErrorItem(BaseModel):
    source: str
    message: str
    occurred_at: datetime


class DataStatusResponse(BaseModel):
    total_transactions: int
    priced_transactions: int
    region_count: int
    latest_collected_at: datetime | None
    region_counts: list[RegionDataCount]
    category_counts: list[CategoryDataCount]
    recent_transactions: list[RecentTransactionItem] = []
    recent_errors: list[CollectionErrorItem] = []


class ReaderGuideItem(BaseModel):
    question: str
    answer: str


class DistributionInsight(BaseModel):
    item: str
    count: int
    q1: int
    median: int
    q3: int
    outlierRate: float
    interpretation: str


class KeywordInsight(BaseModel):
    keyword: str
    count: int
    medianPrice: int
    medianIndex: float
    completionRate: float


class ListingExample(BaseModel):
    item: str
    title: str
    platform: str
    price: int
    status: str
    model: str
    reason: str
    url: str


class LlmCategory(BaseModel):
    name: str
    definition: str
    signals: list[str]
    adminUse: str
    caution: str


class AudienceInsightsResponse(BaseModel):
    asOf: datetime
    population: dict[str, int]
    readerGuide: list[ReaderGuideItem]
    selectionReasons: list[str]
    distributions: list[DistributionInsight]
    keywords: list[KeywordInsight]
    examples: list[ListingExample]
    llmCategories: list[LlmCategory]
    llm: dict[str, str]
    interpretation: dict[str, str]


NoticeStatus = Literal["draft", "published", "hidden"]


class NoticeListItem(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    source: str
    region_name: str | None
    title: str
    status: NoticeStatus
    collected_at: datetime


class NoticeStatusUpdateRequest(BaseModel):
    status: NoticeStatus


class AlertCreatedResponse(BaseModel):
    id: int
    notice_id: int
    created_at: datetime


NoticeListResponse = Page[NoticeListItem]
