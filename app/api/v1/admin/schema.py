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


class ProductClusterInsight(BaseModel):
    cluster: str
    item: str
    model: str
    condition: str
    count: int
    median: int
    q1: int
    q3: int
    platformCount: int
    completedRate: float
    sampleCount: int | None = None
    medianPrice: int | None = None
    iqr: int | None = None
    dispersion: float | None = None
    productFamily: str | None = None
    normalizedModel: str | None = None
    productSignature: str | None = None
    qualityStatus: str | None = "reliable"


class ModelQualityInsight(BaseModel):
    selectedModel: str = "RandomForest"
    r2: float = 0.5000
    mae: int = 56597
    baselineR2: float = -0.1704
    baselineMAE: int = 89595
    validationMethod: str = "시간순 80/20 홀드아웃 및 Group/Random 분할 검증"
    trainCount: int = 3816
    testCount: int = 955


class DataQualityInsight(BaseModel):
    rowsBeforeCleaning: int = 6234
    rowsAfterCleaning: int = 4771
    removedRows: int = 1463
    removedRate: float = 23.47
    invalidPriceRows: int = 259
    accessoryRows: int = 793
    sparseClusterRate: float = 80.6
    noisyClusterRate: float = 7.9
    totalClusters: int = 624
    reliableClusters: int = 38


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
    acceptance: list[str] = Field(default_factory=list)


class AudienceInsightsResponse(BaseModel):
    asOf: datetime
    population: dict[str, int]
    modelQuality: ModelQualityInsight | None = None
    dataQuality: DataQualityInsight | None = None
    readerGuide: list[ReaderGuideItem] = Field(default_factory=list)
    selectionReasons: list[str] = Field(default_factory=list)
    distributions: list[DistributionInsight] = Field(default_factory=list)
    productClusters: list[ProductClusterInsight] = Field(default_factory=list)
    keywords: list[KeywordInsight] = Field(default_factory=list)
    examples: list[ListingExample] = Field(default_factory=list)
    sourceValidation: SourceValidation
    llmCategories: list[LlmCategory] = Field(default_factory=list)
    llm: dict[str, str] = Field(default_factory=dict)
    interpretation: dict[str, str] = Field(default_factory=dict)


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
