import json
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.v1.admin import schema
from app.models.region import Region
from app.models.transaction import Transaction


INSIGHTS_PATH = Path(__file__).resolve().parents[2] / "data" / "admin_audience_insights.json"
if not INSIGHTS_PATH.exists():
    INSIGHTS_PATH = Path(__file__).resolve().parents[3] / "data" / "admin_audience_insights.json"


def get_data_status(db: Session) -> schema.DataStatusResponse:
    total_transactions = db.scalar(select(func.count(Transaction.id))) or 0
    priced_transactions = db.scalar(
        select(func.count(Transaction.id)).where(Transaction.price.is_not(None))
    ) or 0
    region_count = db.scalar(select(func.count(Region.id))) or 0
    latest_collected_at = db.scalar(select(func.max(Transaction.collected_at)))

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
        )
        .group_by(Transaction.category)
        .order_by(func.count(Transaction.id).desc(), Transaction.category)
        .limit(10)
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
        region_counts=[
            schema.RegionDataCount(region_name=name, transaction_count=count)
            for name, count in region_rows
        ],
        category_counts=[
            schema.CategoryDataCount(category=category, transaction_count=count)
            for category, count in category_rows
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
        recent_errors=[],
    )


def get_audience_insights() -> schema.AudienceInsightsResponse:
    return schema.AudienceInsightsResponse.model_validate_json(INSIGHTS_PATH.read_text(encoding="utf-8"))
