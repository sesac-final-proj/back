from datetime import date, datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.v1.admin.service import get_data_status
from app.core.db import Base
from app.models.region import Region
from app.models.transaction import Transaction


def test_data_status_aggregates_live_trade_rows():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine, tables=[Region.__table__, Transaction.__table__])

    with Session(engine) as db:
        region = Region(
            dong_code="1156010100",
            dong_name="당산동",
            gu_name="영등포구",
            lat=37.534,
            lng=126.902,
        )
        db.add(region)
        db.flush()
        db.add_all(
            [
                Transaction(
                    product_title="다이슨 청소기",
                    category="청소기",
                    price=180_000,
                    region_id=region.id,
                    status="판매중",
                    listed_at=date(2026, 9, 1),
                    collected_at=datetime(2026, 9, 8, tzinfo=timezone.utc),
                ),
                Transaction(
                    product_title="쿠쿠 밥솥",
                    category="밥솥",
                    price=None,
                    region_id=None,
                    status="거래완료",
                    listed_at=date(2026, 9, 2),
                    collected_at=datetime(2026, 9, 8, tzinfo=timezone.utc),
                ),
            ]
        )
        db.commit()

        result = get_data_status(db)

    assert result.total_transactions == 2
    assert result.priced_transactions == 1
    assert result.region_count == 1
    assert result.region_counts[0].region_name == "영등포구 당산동"
    assert {item.category for item in result.category_counts} == {"청소기", "밥솥"}
    assert result.recent_transactions[0].product_title in {"다이슨 청소기", "쿠쿠 밥솥"}
    assert result.recent_errors == []
