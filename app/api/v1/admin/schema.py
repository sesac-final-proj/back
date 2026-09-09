from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

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
    priced_count: int = 0
    completed_count: int = 0
    average_price: int | None = None


class StatusDataCount(BaseModel):
    status: str
    transaction_count: int


class DailyTransactionCount(BaseModel):
    date: date
    transaction_count: int


class PriceBandCount(BaseModel):
    label: str
    transaction_count: int


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
    average_price: int | None = None
    unmatched_region_transactions: int = 0
    status_counts: list[StatusDataCount] = Field(default_factory=list)
    daily_counts: list[DailyTransactionCount] = Field(default_factory=list)
    price_band_counts: list[PriceBandCount] = Field(default_factory=list)
    region_counts: list[RegionDataCount]
    category_counts: list[CategoryDataCount]
    recent_transactions: list[RecentTransactionItem] = Field(default_factory=list)
    recent_errors: list[CollectionErrorItem] = Field(default_factory=list)


class DashboardSummary(BaseModel):
    total_transactions: int
    price_eligible_transactions: int
    price_eligible_rate: float
    active_regions: int
    average_listing_price: int | None


class DashboardSource(BaseModel):
    name: str
    status: Literal["available", "empty"]
    last_collected_at: datetime | None


class DashboardOverview(BaseModel):
    summary: DashboardSummary
    collection_trend: list[DailyTransactionCount]
    trade_status: list[StatusDataCount]
    region_ranking: list[RegionDataCount]
    price_distribution: list[PriceBandCount]
    source: DashboardSource
    recent_transactions: list[RecentTransactionItem]


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


class SourceValidationItem(BaseModel):
    id: str
    name: str
    kind: str
    status: str
    rows: int
    pricedRows: int
    modelKnownRate: float
    duplicateIds: int
    datedRate: float


class FutureSourceSlot(BaseModel):
    id: str
    name: str
    status: str
    description: str


class SourceValidation(BaseModel):
    sources: list[SourceValidationItem]
    futureSlots: list[FutureSourceSlot]
    acceptance: list[str]


class AudienceInsightsResponse(BaseModel):
    asOf: datetime
    population: dict[str, int]
    readerGuide: list[ReaderGuideItem]
    selectionReasons: list[str]
    distributions: list[DistributionInsight]
    keywords: list[KeywordInsight]
    examples: list[ListingExample]
    sourceValidation: SourceValidation
    llmCategories: list[LlmCategory]
    llm: dict[str, str]
    interpretation: dict[str, str]


class DreamDistrictSummary(BaseModel):
    district: str
    facilityCount: int
    source: str


class DreamFacilityTypeSummary(BaseModel):
    facilityType: str
    count: int


class DreamStatusResponse(BaseModel):
    totalFacilities: int
    coveredDistricts: int
    configuredDistricts: int
    districts: list[DreamDistrictSummary]
    facilityTypes: list[DreamFacilityTypeSummary]
    sourceFiles: list[str]
    donationDataConnected: bool
    donationMetricStatus: str
    limitations: list[str]


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
