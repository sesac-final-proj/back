"""Point ledger summaries — grouped by the region snapshot on each transaction, not
the user's current profile region (that used to reattribute past points whenever a
user changed neighborhoods, e.g. "영등포구 포인트가 송파구로 바뀜")."""
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.models.point import PointTransaction
from app.models.region import Region


def get_point_summary(db: Session) -> dict:
    district = func.coalesce(Region.gu_name, "지역 미확인")
    rows = (
        db.query(
            district.label("district"),
            func.sum(case((PointTransaction.amount > 0, PointTransaction.amount), else_=0)).label("earned"),
            func.sum(case((PointTransaction.amount < 0, -PointTransaction.amount), else_=0)).label("deducted"),
            func.sum(PointTransaction.amount).label("balance"),
            func.count(PointTransaction.id).label("entries"),
            func.count(func.distinct(PointTransaction.user_id)).label("users"),
        )
        .select_from(PointTransaction)
        .outerjoin(Region, Region.id == PointTransaction.region_id)
        .group_by(district).order_by(district).all()
    )
    return {
        "districts": [dict(row._mapping) for row in rows],
        "earned": sum(row.earned for row in rows),
        "deducted": sum(row.deducted for row in rows),
        "balance": sum(row.balance for row in rows),
        "basis": "전체 포인트 원장 · 적립 당시 동네 스냅샷 기준 · 지역 미확인 포함",
        "caveat": "차감은 기부 집행액을 뜻하지 않습니다. \"지역 미확인\"은 region_id 스냅샷 도입 이전에 적립된 이력입니다.",
    }
