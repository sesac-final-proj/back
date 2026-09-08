from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.api.v1.admin import schema
from app.models.region import Region
from app.models.transaction import Transaction

# 최근 오류 목록에 몇 건까지 보여줄지 — 페이지네이션 요구사항 없어(문서 DoD 참고)
# 과설계 없이 상수 하나로 처리.
RECENT_ERROR_LIMIT = 20

UNMATCHED_REGION_LABEL = "지역 매칭 실패"


def _error_rate(normal: int, error: int) -> float:
    total = normal + error
    return round(error / total, 4) if total else 0.0


def get_data_status(db: Session) -> schema.DataStatusResponse:
    # 지역별: 매칭된 것들은 실제 Region으로 묶고, region_id가 없는(매칭 실패) 건은
    # 한 행으로 합친다 — 특정 "지역"이 아니라 크롤링 매칭 자체의 실패라서.
    region_rows = (
        db.query(Region.dong_name, func.count(Transaction.id))
        .join(Transaction, Transaction.region_id == Region.id)
        .group_by(Region.dong_name)
        .order_by(func.count(Transaction.id).desc())
        .all()
    )
    region_counts = [
        schema.RegionDataCount(region_name=dong_name, normal_count=count, error_count=0, error_rate=0.0)
        for dong_name, count in region_rows
    ]
    unmatched_count = db.query(func.count(Transaction.id)).filter(Transaction.region_id.is_(None)).scalar() or 0
    if unmatched_count:
        region_counts.append(
            schema.RegionDataCount(
                region_name=UNMATCHED_REGION_LABEL,
                normal_count=0,
                error_count=unmatched_count,
                error_rate=1.0,
            )
        )

    # 카테고리별: 같은 매칭 실패 기준을 카테고리 단위로 교차 집계.
    is_error = case((Transaction.region_id.is_(None), 1), else_=0)
    category_rows = (
        db.query(Transaction.category, func.sum(1 - is_error), func.sum(is_error))
        .group_by(Transaction.category)
        .order_by(func.count(Transaction.id).desc())
        .all()
    )
    category_counts = [
        schema.CategoryDataCount(
            category=category,
            normal_count=int(normal or 0),
            error_count=int(error or 0),
            error_rate=_error_rate(int(normal or 0), int(error or 0)),
        )
        for category, normal, error in category_rows
    ]

    # 최근 오류: region_id 없는(매칭 실패) 건 중 최근 크롤링분 — 원본 "지역" 텍스트는
    # Transaction에 안 남아있어서(seed_transactions.py 참고) 상품명으로 대신 표시.
    recent_error_rows = (
        db.query(Transaction)
        .filter(Transaction.region_id.is_(None))
        .order_by(Transaction.collected_at.desc())
        .limit(RECENT_ERROR_LIMIT)
        .all()
    )
    recent_errors = [
        schema.CollectionErrorItem(
            source="daangn_crawler",
            message=f"'{t.product_title}' 지역 매칭 실패",
            occurred_at=t.collected_at,
        )
        for t in recent_error_rows
    ]

    return schema.DataStatusResponse(
        region_counts=region_counts,
        category_counts=category_counts,
        recent_errors=recent_errors,
    )
