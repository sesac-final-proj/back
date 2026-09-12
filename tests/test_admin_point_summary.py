from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.core.db import Base
from app.models.user import User
from app.models.region import Region
from app.models.point import PointTransaction
from app.api.v1.admin.point_summary import get_point_summary


def test_point_ledger_reconciles_districts_and_unknown_region():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine, tables=[Region.__table__, User.__table__, PointTransaction.__table__])
    with Session(engine) as db:
        assert get_point_summary(db)["balance"] == 0
        region = Region(dong_code="test", dong_name="테스트동", gu_name="송파구", lat=37.5, lng=127.1)
        db.add(region); db.flush()
        known = User(email="known@example.com", nickname="지역 사용자", region_id=region.id)
        unknown = User(email="unknown@example.com", nickname="지역 미확인")
        db.add_all([known, unknown]); db.flush()
        db.add_all([PointTransaction(user_id=known.id, amount=100, source="trade"), PointTransaction(user_id=known.id, amount=-20, source="adjustment"), PointTransaction(user_id=unknown.id, amount=50, source="trade")]); db.commit()
        result = get_point_summary(db)
        assert (result["earned"], result["deducted"], result["balance"]) == (150, 20, 130)
        assert sum(row["entries"] for row in result["districts"]) == 3
        assert sum(row["balance"] for row in result["districts"]) == result["balance"]
        assert next(row for row in result["districts"] if row["district"] == "송파구")["users"] == 1
        assert next(row for row in result["districts"] if row["district"] == "지역 미확인")["earned"] == 50
