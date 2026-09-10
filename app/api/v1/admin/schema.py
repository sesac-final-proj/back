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


class GuStatusDataCount(BaseModel):
    gu_name: str
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
    trade_status_by_gu: list[GuStatusDataCount] = Field(default_factory=list)
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


# --------------------------------------------------------------------------
# 가격예측 모델 대시보드 (docs/issue/12-price-prediction-dashboard.md)
# --------------------------------------------------------------------------


class PriceModelMetricItem(BaseModel):
    model_config = {"from_attributes": True}

    feature_set: str
    model_key: str
    label: str
    rmse: float
    mae: float
    mape: float
    r2: float
    hit10: float
    hit20: float
    extra: dict | None = None


class PriceModelMetricsResponse(BaseModel):
    metrics: list[PriceModelMetricItem]


class PriceModelListingItem(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    category: str
    detail_type: str
    gu: str
    condition: str
    status: str
    chat_count: int
    interest_count: int
    view_count: float
    manner_temp: float
    title_length: int
    days_since_listed: int
    category_detail_median_price: float
    price: int
    price_log: float
    title: str


PriceModelListingListResponse = Page[PriceModelListingItem]


class PriceDistributionTypeSummary(BaseModel):
    type: str
    count: int
    median_price: float


class PriceDistributionPoint(BaseModel):
    type: str
    price: int


class PriceDistributionCategory(BaseModel):
    category: str
    sample_count: int
    types: list[PriceDistributionTypeSummary]
    points: list[PriceDistributionPoint]


class PriceDistributionResponse(BaseModel):
    categories: list[PriceDistributionCategory]


class DetailTypeCountItem(BaseModel):
    category: str
    detail_type: str
    count: int


class DetailTypeCountsResponse(BaseModel):
    items: list[DetailTypeCountItem]


class PricePredictionItem(BaseModel):
    model_config = {"from_attributes": True}

    feature_set: str
    category: str
    detail_type: str
    title: str
    actual_price: int
    predicted_price: int
    error_rate: float


class PricePlatformComparisonItem(BaseModel):
    model_config = {"from_attributes": True}

    category: str
    platform: str
    sample_count: int
    mean_price: float
    median_price: float
    std_price: float
    p25_price: float
    p75_price: float


class PricePlatformTestItem(BaseModel):
    model_config = {"from_attributes": True}

    category: str
    platform_a: str
    platform_b: str
    median_a: float
    median_b: float
    diff_pct: float
    p_value: float
    significant: bool


class PriceClusterItem(BaseModel):
    model_config = {"from_attributes": True}

    category: str
    price_band: str
    share: float
    median_price: float
    range_low: float
    range_high: float
    sample_count: int


class PriceFeatureImportanceItem(BaseModel):
    model_config = {"from_attributes": True}

    feature_set: str
    feature: str
    gain: float
    split: int


class PriceModelChartsResponse(BaseModel):
    predictions: list[PricePredictionItem]
    platform_comparisons: list[PricePlatformComparisonItem]
    platform_tests: list[PricePlatformTestItem]
    clusters: list[PriceClusterItem]
    feature_importance: list[PriceFeatureImportanceItem]


# --------------------------------------------------------------------------
# 가격 지역별 비교 대시보드 (crawling_Data 세션 산출물, price_model과 별개 기능)
# --------------------------------------------------------------------------


class PriceComparisonCategoryItem(BaseModel):
    model_config = {"from_attributes": True}

    category: str
    sample_count: int
    median_price: float
    std_price: float
    cv_price: float
    price_trend_pct: float | None
    frequency_grade: str
    listings_per_month: float


class PriceComparisonRegionItem(BaseModel):
    model_config = {"from_attributes": True}

    category: str
    gu: str
    sample_count: int
    median_price: float
    completion_rate: float
    avg_manner_temp: float


class PriceComparisonDetailTypeItem(BaseModel):
    model_config = {"from_attributes": True}

    category: str
    detail_type: str
    gu: str
    sample_count: int
    median_price: float
    cv_price: float


class PriceComparisonOverviewResponse(BaseModel):
    categories: list[PriceComparisonCategoryItem]
    regions: list[PriceComparisonRegionItem]
    detail_types: list[PriceComparisonDetailTypeItem]


class PriceComparisonSampleItem(BaseModel):
    model_config = {"from_attributes": True}

    gu: str
    price: int


class PriceComparisonSamplesResponse(BaseModel):
    category: str
    samples: list[PriceComparisonSampleItem]


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
