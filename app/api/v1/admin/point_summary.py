"""Point ledger summaries use one current primary region per user, without join fan-out."""
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.models.point import PointTransaction
from app.models.region import Region
from app.models.user import User


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
        .outerjoin(User, User.id == PointTransaction.user_id)
        .outerjoin(Region, Region.id == User.region_id)
        .group_by(district).order_by(district).all()
    )
    return {
        "districts": [dict(row._mapping) for row in rows],
        "earned": sum(row.earned for row in rows),
        "deducted": sum(row.deducted for row in rows),
        "balance": sum(row.balance for row in rows),
        "basis": "전체 포인트 원장 · 사용자 현재 대표 동네 기준 · 지역 미확인 포함",
        "caveat": "적립 당시 지역 이력이 없어 동네 변경 시 구별 귀속이 바뀝니다. 차감은 기부 집행액을 뜻하지 않습니다.",
    }
