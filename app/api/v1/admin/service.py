import json
import csv
import random
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.api.v1.admin import schema
from app.models.price_model import (
    PriceCluster,
    PriceFeatureImportance,
    PriceModelListing,
    PriceModelMetric,
    PricePlatformComparison,
    PricePlatformTest,
    PricePrediction,
)
from app.models.price_distribution import (
    PriceCategorySummary,
    PriceDetailTypeStat,
    PriceListingSample,
    PriceRegionStat,
)
from app.models.region import Region
from app.models.transaction import Transaction
from app.api.v1.dream.service import CSV_PATH, JSON_412_PATH, JSON_PARSED_PATH, DISTRICT_SERVICES

# price-distribution에서 세부유형을 몇 개까지 이름 유지하고 나머지를 "기타"로 묶을지.
PRICE_DISTRIBUTION_TOP_TYPES = 5
PRICE_DISTRIBUTION_DEFAULT_SAMPLE = 2000


INSIGHTS_PATH = Path(__file__).resolve().parents[2] / "data" / "admin_audience_insights.json"
if not INSIGHTS_PATH.exists():
    INSIGHTS_PATH = Path(__file__).resolve().parents[3] / "data" / "admin_audience_insights.json"


def get_dashboard_overview(db: Session) -> schema.DashboardOverview:
    # Reuse the existing transaction/region aggregates; no duplicate storage.
    data = get_data_status(db)
    today = datetime.now(timezone.utc).date()
    first_day = today - timedelta(days=13)
    rows = db.execute(
        select(func.date(Transaction.collected_at), func.count(Transaction.id))
        .where(Transaction.collected_at >= first_day, Transaction.collected_at < today + timedelta(days=1))
        .group_by(func.date(Transaction.collected_at))
    ).all()
    counts = {str(day): count for day, count in rows}
    return schema.DashboardOverview(
        summary=schema.DashboardSummary(
            total_transactions=data.total_transactions,
            price_eligible_transactions=data.priced_transactions,
            price_eligible_rate=round(data.priced_transactions / data.total_transactions * 100, 1) if data.total_transactions else 0,
            active_regions=data.region_count,
            average_listing_price=data.average_price,
        ),
        collection_trend=[schema.DailyTransactionCount(
            date=first_day + timedelta(days=i),
            transaction_count=counts.get(str(first_day + timedelta(days=i)), 0),
        ) for i in range(14)],
        trade_status=data.status_counts,
        region_ranking=data.region_counts[:5],
        price_distribution=data.price_band_counts,
        source=schema.DashboardSource(name="당근 수집 거래", status="available" if data.total_transactions else "empty", last_collected_at=data.latest_collected_at),
        recent_transactions=data.recent_transactions,
    )


def get_data_status(db: Session) -> schema.DataStatusResponse:
    total_transactions = db.scalar(select(func.count(Transaction.id))) or 0
    priced_transactions = db.scalar(
        select(func.count(Transaction.id)).where(Transaction.price.is_not(None))
    ) or 0
    region_count = db.scalar(
        select(func.count(func.distinct(Transaction.region_id))).where(
            Transaction.region_id.is_not(None)
        )
    ) or 0
    latest_collected_at = db.scalar(select(func.max(Transaction.collected_at)))
    average_price_value = db.scalar(
        select(func.avg(Transaction.price)).where(Transaction.price.is_not(None))
    )
    average_price = round(float(average_price_value)) if average_price_value is not None else None
    unmatched_region_transactions = db.scalar(
        select(func.count(Transaction.id)).where(Transaction.region_id.is_(None))
    ) or 0

    status_rows = db.execute(
        select(Transaction.status, func.count(Transaction.id).label("transaction_count"))
        .group_by(Transaction.status)
        .order_by(func.count(Transaction.id).desc(), Transaction.status)
    ).all()

    latest_day = latest_collected_at.date() if latest_collected_at else date.today()
    first_day = latest_day - timedelta(days=13)
    daily_rows = db.execute(
        select(
            func.date(Transaction.collected_at).label("collected_date"),
            func.count(Transaction.id).label("transaction_count"),
        )
        .where(Transaction.collected_at >= first_day)
        .group_by(func.date(Transaction.collected_at))
        .order_by(func.date(Transaction.collected_at))
    ).all()
    daily_lookup = {date.fromisoformat(str(day)): count for day, count in daily_rows}

    price_band = case(
        (Transaction.price < 50_000, "5만원 미만"),
        (Transaction.price < 100_000, "5–10만원"),
        (Transaction.price < 300_000, "10–30만원"),
        (Transaction.price < 500_000, "30–50만원"),
        else_="50만원 이상",
    )
    price_band_rows = db.execute(
        select(price_band.label("price_band"), func.count(Transaction.id))
        .where(Transaction.price.is_not(None))
        .group_by(price_band)
    ).all()
    price_band_lookup = dict(price_band_rows)
    price_band_order = ["5만원 미만", "5–10만원", "10–30만원", "30–50만원", "50만원 이상"]

    region_rows = db.execute(
        select(
            (Region.gu_name + " " + Region.dong_name).label("region_name"),
            func.count(Transaction.id).label("transaction_count"),
        )
        .join(Transaction, Transaction.region_id == Region.id)
        .group_by(Region.id, Region.gu_name, Region.dong_name)
        .order_by(func.count(Transaction.id).desc(), Region.gu_name, Region.dong_name)
        .limit(12)
    ).all()

    category_rows = db.execute(
        select(
            Transaction.category,
            func.count(Transaction.id).label("transaction_count"),
            func.count(Transaction.price).label("priced_count"),
            func.sum(
                case((Transaction.status.in_(["거래완료", "판매완료", "완료", "sold"]), 1), else_=0)
            ).label("completed_count"),
            func.avg(Transaction.price).label("average_price"),
        )
        .group_by(Transaction.category)
        .order_by(func.count(Transaction.id).desc(), Transaction.category)
        .limit(8)
    ).all()

    recent_rows = db.execute(
        select(Transaction, Region.gu_name, Region.dong_name)
        .outerjoin(Region, Transaction.region_id == Region.id)
        .order_by(Transaction.collected_at.desc(), Transaction.id.desc())
        .limit(8)
    ).all()

    return schema.DataStatusResponse(
        total_transactions=total_transactions,
        priced_transactions=priced_transactions,
        region_count=region_count,
        latest_collected_at=latest_collected_at,
        average_price=average_price,
        unmatched_region_transactions=unmatched_region_transactions,
        status_counts=[
            schema.StatusDataCount(status=status or "상태 미확인", transaction_count=count)
            for status, count in status_rows
        ],
        daily_counts=[
            schema.DailyTransactionCount(
                date=first_day + timedelta(days=offset),
                transaction_count=daily_lookup.get(first_day + timedelta(days=offset), 0),
            )
            for offset in range(14)
        ],
        price_band_counts=[
            schema.PriceBandCount(label=label, transaction_count=price_band_lookup.get(label, 0))
            for label in price_band_order
        ],
        region_counts=[
            schema.RegionDataCount(region_name=name, transaction_count=count)
            for name, count in region_rows
        ],
        category_counts=[
            schema.CategoryDataCount(
                category=category,
                transaction_count=count,
                priced_count=priced_count,
                completed_count=completed_count or 0,
                average_price=round(float(category_average)) if category_average is not None else None,
            )
            for category, count, priced_count, completed_count, category_average in category_rows
        ],
        recent_transactions=[
            schema.RecentTransactionItem(
                id=transaction.id,
                product_title=transaction.product_title,
                category=transaction.category,
                price=transaction.price,
                region_name=(
                    f"{gu_name} {dong_name}" if gu_name and dong_name else None
                ),
                status=transaction.status,
                listed_at=transaction.listed_at,
                collected_at=transaction.collected_at,
            )
            for transaction, gu_name, dong_name in recent_rows
        ],
        recent_errors=[
            schema.CollectionErrorItem(
                source="당근 거래 수집",
                message=f"지역 매칭 실패 · #{transaction.id} {transaction.product_title}",
                occurred_at=transaction.collected_at,
            )
            for transaction in db.scalars(
                select(Transaction)
                .where(Transaction.region_id.is_(None))
                .order_by(Transaction.collected_at.desc(), Transaction.id.desc())
                .limit(5)
            )
        ],
    )


def get_audience_insights() -> schema.AudienceInsightsResponse:
    return schema.AudienceInsightsResponse.model_validate_json(INSIGHTS_PATH.read_text(encoding="utf-8"))


def get_dream_status() -> schema.DreamStatusResponse:
    district_counts: Counter[str] = Counter()
    type_counts: Counter[str] = Counter()
    district_sources: dict[str, str] = {}
    sources: list[str] = []

    if JSON_412_PATH.exists():
        centers = json.loads(JSON_412_PATH.read_text(encoding="utf-8"))
        for center in centers:
            district = (center.get("district") or "").strip()
            if district:
                district_counts[district] += 1
                district_sources[district] = "서울 시설 JSON"
        sources.append(JSON_412_PATH.name)

    if CSV_PATH.exists():
        rows: list[dict[str, str]] = []
        for encoding in ("cp949", "euc-kr", "utf-8-sig", "utf-8"):
            try:
                with CSV_PATH.open("r", encoding=encoding, newline="") as file:
                    rows = list(csv.DictReader(file))
                break
            except UnicodeDecodeError:
                continue
        for row in rows:
            status_name = (row.get("영업상태명") or "").strip()
            if status_name and "운영" not in status_name:
                continue
            address = row.get("소재지전체주소") or row.get("도로명전체주소") or ""
            district = next((name for name in DISTRICT_SERVICES if name in address), "")
            if district and not JSON_412_PATH.exists():
                district_counts[district] += 1
                district_sources[district] = "CSV"
            if district and not JSON_PARSED_PATH.exists():
                type_counts[(row.get("복지시설종류명") or "아동복지시설").strip()] += 1
        sources.append(CSV_PATH.name)

    if JSON_PARSED_PATH.exists():
        parsed = json.loads(JSON_PARSED_PATH.read_text(encoding="utf-8"))
        for district, rows in parsed.items():
            if not district_counts[district]:
                district_counts[district] = len(rows)
                district_sources[district] = "파싱 JSON"
            for row in rows:
                type_counts[(row.get("kind") or "지역아동센터").strip()] += 1
        sources.append(JSON_PARSED_PATH.name)

    return schema.DreamStatusResponse(
        totalFacilities=sum(district_counts.values()),
        coveredDistricts=sum(count > 0 for count in district_counts.values()),
        configuredDistricts=len(DISTRICT_SERVICES),
        districts=[
            schema.DreamDistrictSummary(
                district=district,
                facilityCount=count,
                source=district_sources[district],
            )
            for district, count in district_counts.most_common()
        ],
        facilityTypes=[schema.DreamFacilityTypeSummary(facilityType=name, count=count) for name, count in type_counts.most_common(10)],
        sourceFiles=sources,
        donationDataConnected=False,
        donationMetricStatus="기부 설정·내역·집행 저장 API 미구현",
        limitations=[
            "현재 시설 데이터는 운영 대상 탐색용이며 기부 실적 데이터가 아닙니다.",
            "시설 유형 구성은 세부 유형이 있는 CSV·파싱 JSON 범위이며 412개 전체의 유형 분포가 아닙니다.",
            "프론트의 donationCount, currentAmount, targetAmount는 현재 0 기본값입니다.",
            "기부 성과 분석은 거래-기부 원장과 집행 원장이 연결된 뒤 활성화해야 합니다.",
        ],
    )


# --------------------------------------------------------------------------
# 가격예측 모델 대시보드 (docs/issue/12-price-prediction-dashboard.md)
# scripts/seed_price_model_data.py로 analyzer/outputs/*를 DB에 적재해둔 걸 읽기만 한다.
# --------------------------------------------------------------------------


def get_price_model_metrics(db: Session) -> schema.PriceModelMetricsResponse:
    rows = db.query(PriceModelMetric).order_by(PriceModelMetric.feature_set, PriceModelMetric.model_key).all()
    return schema.PriceModelMetricsResponse(
        metrics=[schema.PriceModelMetricItem.model_validate(r) for r in rows]
    )


def list_price_model_listings(
    db: Session, category: str | None, detail_type: str | None, page: int, size: int
) -> schema.PriceModelListingListResponse:
    query = db.query(PriceModelListing)
    if category:
        query = query.filter(PriceModelListing.category == category)
    if detail_type:
        query = query.filter(PriceModelListing.detail_type == detail_type)
    total = query.count()
    rows = (
        query.order_by(PriceModelListing.id)
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )
    return schema.PriceModelListingListResponse(
        items=[schema.PriceModelListingItem.model_validate(r) for r in rows], total=total
    )


def get_price_distribution(
    db: Session, category: str | None, sample: int
) -> schema.PriceDistributionResponse:
    """세부유형별 가격분포(스웜 플롯 원본) — 건수 상위 N개 세부유형만 이름을 유지하고
    나머지는 "기타"로 묶어서, 카테고리별 전체 표본 중 최대 sample건만 흩뿌린다."""
    query = db.query(PriceModelListing)
    if category:
        query = query.filter(PriceModelListing.category == category)
    listings = query.all()

    by_category: dict[str, list[PriceModelListing]] = {}
    for listing in listings:
        by_category.setdefault(listing.category, []).append(listing)

    categories = []
    for cat_name, cat_listings in by_category.items():
        type_counts = Counter(item.detail_type for item in cat_listings)
        top_types = {t for t, _ in type_counts.most_common(PRICE_DISTRIBUTION_TOP_TYPES)}

        prices_by_type: dict[str, list[int]] = {}
        for item in cat_listings:
            bucket = item.detail_type if item.detail_type in top_types else "기타"
            prices_by_type.setdefault(bucket, []).append(item.price)

        types_summary = [
            schema.PriceDistributionTypeSummary(
                type=type_name,
                count=len(prices),
                median_price=sorted(prices)[len(prices) // 2],
            )
            for type_name, prices in sorted(prices_by_type.items(), key=lambda kv: -len(kv[1]))
        ]

        points = [
            schema.PriceDistributionPoint(
                type=item.detail_type if item.detail_type in top_types else "기타",
                price=item.price,
            )
            for item in cat_listings
        ]
        if len(points) > sample:
            points = random.sample(points, sample)

        categories.append(
            schema.PriceDistributionCategory(
                category=cat_name,
                sample_count=len(cat_listings),
                types=types_summary,
                points=points,
            )
        )

    return schema.PriceDistributionResponse(categories=categories)


def get_price_model_charts(db: Session) -> schema.PriceModelChartsResponse:
    """산점도(예측vs실제)/플랫폼비교/유의성검정/가격군집/피처중요도 — 전부 소규모
    스냅샷이라 페이지네이션 없이 한 번에 묶어서 내려준다(기존 admin/data-status와
    같은 패턴)."""
    predictions = db.query(PricePrediction).order_by(PricePrediction.feature_set, PricePrediction.id).all()
    comparisons = (
        db.query(PricePlatformComparison)
        .order_by(PricePlatformComparison.category, PricePlatformComparison.platform)
        .all()
    )
    tests = db.query(PricePlatformTest).order_by(PricePlatformTest.category).all()
    clusters = db.query(PriceCluster).order_by(PriceCluster.category, PriceCluster.median_price).all()
    feature_importance = (
        db.query(PriceFeatureImportance)
        .order_by(PriceFeatureImportance.feature_set, PriceFeatureImportance.gain.desc())
        .all()
    )

    return schema.PriceModelChartsResponse(
        predictions=[schema.PricePredictionItem.model_validate(r) for r in predictions],
        platform_comparisons=[schema.PricePlatformComparisonItem.model_validate(r) for r in comparisons],
        platform_tests=[schema.PricePlatformTestItem.model_validate(r) for r in tests],
        clusters=[schema.PriceClusterItem.model_validate(r) for r in clusters],
        feature_importance=[schema.PriceFeatureImportanceItem.model_validate(r) for r in feature_importance],
    )


# --------------------------------------------------------------------------
# 가격 지역별 비교 대시보드 (crawling_Data 세션 산출물, price_model과 별개 기능)
# --------------------------------------------------------------------------


def get_price_comparison_overview(db: Session) -> schema.PriceComparisonOverviewResponse:
    """카테고리 요약/지역별/세부유형별 통계 — scripts/seed_price_distribution_data.py가
    미리 집계해둔 스냅샷 그대로 반환(전부 소규모라 페이지네이션 없이 한 번에)."""
    categories = db.query(PriceCategorySummary).order_by(PriceCategorySummary.category).all()
    regions = db.query(PriceRegionStat).order_by(PriceRegionStat.category, PriceRegionStat.gu).all()
    detail_types = (
        db.query(PriceDetailTypeStat)
        .order_by(PriceDetailTypeStat.category, PriceDetailTypeStat.detail_type, PriceDetailTypeStat.gu)
        .all()
    )

    return schema.PriceComparisonOverviewResponse(
        categories=[schema.PriceComparisonCategoryItem.model_validate(r) for r in categories],
        regions=[schema.PriceComparisonRegionItem.model_validate(r) for r in regions],
        detail_types=[schema.PriceComparisonDetailTypeItem.model_validate(r) for r in detail_types],
    )


def get_price_comparison_samples(
    db: Session, category: str, gu: str | None, sample: int
) -> schema.PriceComparisonSamplesResponse:
    """카테고리 하나의 매물 표본(구별 스웜 플롯용) — seed 단계에서 이미 이상치 제외/
    구별 최대 600건으로 추려둔 값이라, sample은 그 이상을 추가로 솎아낼 때만 쓰인다."""
    query = db.query(PriceListingSample).filter(PriceListingSample.category == category)
    if gu:
        query = query.filter(PriceListingSample.gu == gu)
    rows = query.all()
    if len(rows) > sample:
        rows = random.sample(rows, sample)

    return schema.PriceComparisonSamplesResponse(
        category=category,
        samples=[schema.PriceComparisonSampleItem.model_validate(r) for r in rows],
    )
