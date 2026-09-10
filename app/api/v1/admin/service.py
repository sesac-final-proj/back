import json
import csv
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from app.api.v1.admin import schema
from app.models.notice import AdminNotice, AdminNoticeAlert
from app.models.region import Region
from app.models.transaction import Transaction
from app.models.user import User, UserRole
from app.api.v1.dream.service import CSV_PATH, JSON_412_PATH, JSON_PARSED_PATH, DISTRICT_SERVICES


INSIGHTS_PATH = Path(__file__).resolve().parents[2] / "data" / "admin_audience_insights.json"
if not INSIGHTS_PATH.exists():
    INSIGHTS_PATH = Path(__file__).resolve().parents[3] / "data" / "admin_audience_insights.json"


def _notice_status(notice: AdminNotice, now: datetime | None = None) -> schema.NoticeStatus:
    if notice.manual_status == "hidden":
        return "hidden"
    now = now or datetime.now(timezone.utc)
    starts_at = notice.starts_at
    ends_at = notice.ends_at
    if starts_at is not None and starts_at.tzinfo is None:
        starts_at = starts_at.replace(tzinfo=timezone.utc)
    if ends_at is not None and ends_at.tzinfo is None:
        ends_at = ends_at.replace(tzinfo=timezone.utc)
    if starts_at is None:
        return "draft"
    if starts_at > now:
        return "scheduled"
    if ends_at is not None and ends_at < now:
        return "ended"
    return "published"


def _warning_reasons(notice: AdminNotice, status: schema.NoticeStatus, now: datetime | None = None) -> list[str]:
    now = now or datetime.now(timezone.utc)
    reasons: list[str] = []
    if not notice.title.strip() or not notice.content.strip() or not notice.service:
        reasons.append("필수 정보 누락")
    if notice.starts_at is None:
        reasons.append("시작일 없음")
    starts_at = notice.starts_at.replace(tzinfo=timezone.utc) if notice.starts_at and notice.starts_at.tzinfo is None else notice.starts_at
    ends_at = notice.ends_at.replace(tzinfo=timezone.utc) if notice.ends_at and notice.ends_at.tzinfo is None else notice.ends_at
    if starts_at and starts_at < now and notice.manual_status == "draft":
        reasons.append("시작일 지났는데 작성중")
    if ends_at and status == "published":
        remaining = ends_at - now
        if timedelta(0) <= remaining <= timedelta(days=3):
            days = max(0, remaining.days)
            reasons.append(f"종료 {days}일 전")
    if ends_at and ends_at < now and notice.manual_status == "published":
        reasons.append("종료일 지났는데 게시중")
    return reasons


def _notice_item(notice: AdminNotice, now: datetime | None = None) -> schema.NoticeListItem:
    now = now or datetime.now(timezone.utc)
    status = _notice_status(notice, now)
    return schema.NoticeListItem(
        id=notice.id,
        service=notice.service,
        title=notice.title,
        content=notice.content,
        status=status,
        manual_status=notice.manual_status,
        starts_at=notice.starts_at,
        ends_at=notice.ends_at,
        display_order=notice.display_order,
        alert_count=notice.alert_count,
        warning_reasons=_warning_reasons(notice, status, now),
        created_at=notice.created_at,
        updated_at=notice.updated_at,
        deleted_at=notice.deleted_at,
    )


def list_notices(
    db: Session,
    q: str | None = None,
    service: str | None = None,
    status: str | None = None,
    delete_status: str | None = None,
    page: int = 1,
    size: int = 10,
) -> schema.NoticeListResponse:
    query = db.query(AdminNotice)
    if delete_status == "deleted":
        query = query.filter(AdminNotice.deleted_at.is_not(None))
    elif delete_status != "all":
        query = query.filter(AdminNotice.deleted_at.is_(None))
    if q:
        keyword = f"%{q.strip()}%"
        query = query.filter(or_(AdminNotice.title.ilike(keyword), AdminNotice.content.ilike(keyword)))
    if service in ("dream", "carrot"):
        query = query.filter(AdminNotice.service == service)
    rows = query.order_by(AdminNotice.display_order.asc(), AdminNotice.created_at.desc(), AdminNotice.id.desc()).all()
    now = datetime.now(timezone.utc)
    items = [_notice_item(row, now) for row in rows]
    if status in ("draft", "scheduled", "published", "ended", "hidden"):
        items = [item for item in items if item.status == status]
    total = len(items)
    start = (page - 1) * size
    return schema.NoticeListResponse(items=items[start:start + size], total=total)


def create_notice(db: Session, admin: User, payload: schema.NoticeCreateRequest) -> schema.NoticeListItem:
    max_order = db.scalar(select(func.max(AdminNotice.display_order)).where(AdminNotice.deleted_at.is_(None))) or 0
    notice = AdminNotice(
        service=payload.service,
        title=payload.title.strip(),
        content=payload.content.strip(),
        starts_at=payload.starts_at,
        ends_at=payload.ends_at,
        manual_status=payload.manual_status,
        display_order=max_order + 1,
        created_by=admin.id,
        updated_by=admin.id,
    )
    db.add(notice)
    db.commit()
    db.refresh(notice)
    return _notice_item(notice)


def update_notice(db: Session, admin: User, notice_id: int, payload: schema.NoticeUpdateRequest) -> schema.NoticeListItem:
    notice = db.query(AdminNotice).filter(AdminNotice.id == notice_id, AdminNotice.deleted_at.is_(None)).first()
    if notice is None:
        raise ValueError("notice_not_found")
    fields = payload.model_fields_set
    for field in ("service", "title", "content", "starts_at", "ends_at", "manual_status"):
        if field not in fields:
            continue
        value = getattr(payload, field)
        setattr(notice, field, value.strip() if isinstance(value, str) and field in {"title", "content"} else value)
    notice.updated_by = admin.id
    db.commit()
    db.refresh(notice)
    return _notice_item(notice)


def soft_delete_notice(db: Session, admin: User, notice_id: int) -> None:
    notice = db.query(AdminNotice).filter(AdminNotice.id == notice_id, AdminNotice.deleted_at.is_(None)).first()
    if notice is None:
        raise ValueError("notice_not_found")
    notice.deleted_at = datetime.now(timezone.utc)
    notice.deleted_by = admin.id
    notice.updated_by = admin.id
    db.commit()


def duplicate_notice(db: Session, admin: User, notice_id: int) -> schema.NoticeListItem:
    original = db.query(AdminNotice).filter(AdminNotice.id == notice_id, AdminNotice.deleted_at.is_(None)).first()
    if original is None:
        raise ValueError("notice_not_found")
    max_order = db.scalar(select(func.max(AdminNotice.display_order)).where(AdminNotice.deleted_at.is_(None))) or 0
    notice = AdminNotice(
        service=original.service,
        title=f"{original.title} 복사본",
        content=original.content,
        manual_status=None,
        starts_at=None,
        ends_at=None,
        display_order=max_order + 1,
        alert_count=0,
        created_by=admin.id,
        updated_by=admin.id,
    )
    db.add(notice)
    db.commit()
    db.refresh(notice)
    return _notice_item(notice)


def create_notice_alerts(db: Session, notice_id: int) -> schema.AlertCreatedResponse:
    notice = db.query(AdminNotice).filter(AdminNotice.id == notice_id, AdminNotice.deleted_at.is_(None)).first()
    if notice is None:
        raise ValueError("notice_not_found")
    existing_user_ids = {
        row[0] for row in db.execute(select(AdminNoticeAlert.user_id).where(AdminNoticeAlert.notice_id == notice_id)).all()
    }
    users = db.scalars(select(User).where(User.role == UserRole.USER)).all()
    created = 0
    for user in users:
        if user.id in existing_user_ids:
            continue
        db.add(AdminNoticeAlert(notice_id=notice_id, user_id=user.id))
        created += 1
    notice.alert_count += created
    db.commit()
    db.refresh(notice)
    return schema.AlertCreatedResponse(notice_id=notice.id, created_count=created, alert_count=notice.alert_count, created_at=datetime.now(timezone.utc))


def reorder_notices(db: Session, admin: User, payload: schema.NoticeOrderRequest) -> schema.NoticeListResponse:
    notices = db.query(AdminNotice).filter(AdminNotice.id.in_(payload.notice_ids), AdminNotice.deleted_at.is_(None)).all()
    by_id = {notice.id: notice for notice in notices}
    for index, notice_id in enumerate(payload.notice_ids, start=1):
        if notice_id in by_id:
            by_id[notice_id].display_order = index
            by_id[notice_id].updated_by = admin.id
    db.commit()
    return list_notices(db, page=1, size=10)


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
