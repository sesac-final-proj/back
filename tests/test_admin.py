"""Admin 데이터 현황(GET /api/v1/admin/data-status) 자가 점검.

python -m tests.test_admin 로 실행. 실 DB에 임시 지역/거래 데이터를 만들었다가
끝나면 지운다. require_admin 게이트(일반 유저 403)까지 HTTP 레벨로 확인한다.
"""
from datetime import date

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api.v1.admin import service as admin_service
from app.core.db import SessionLocal
from app.core.deps import require_admin
from app.core.security import hash_password
from app.main import app
from app.models.region import Region
from app.models.transaction import Transaction
from app.models.user import User, UserRole


def main():
    db = SessionLocal()
    region = Region(dong_code="__ADMIN_SELFCHECK__", dong_name="관리자검증동", gu_name="검증구", lat=0.0, lng=0.0)
    admin_user = User(
        email="__admin_selfcheck__@example.com",
        password_hash=hash_password("x"),
        nickname="admin_selfcheck",
        role=UserRole.ADMIN,
    )
    normal_user = User(
        email="__admin_selfcheck_user__@example.com",
        password_hash=hash_password("x"),
        nickname="user_selfcheck",
        role=UserRole.USER,
    )
    db.add_all([region, admin_user, normal_user])
    db.commit()
    db.refresh(region)
    db.refresh(admin_user)
    db.refresh(normal_user)

    tx_ids: list[int] = []
    try:
        rows = [
            Transaction(product_title="검증동 청소기 1", category="청소기", region_id=region.id, status="거래중", listed_at=date.today()),
            Transaction(product_title="검증동 청소기 2", category="청소기", region_id=region.id, status="거래중", listed_at=date.today()),
            Transaction(product_title="매칭실패 청소기", category="청소기", region_id=None, status="거래중", listed_at=date.today()),
            Transaction(product_title="매칭실패 의류", category="의류", region_id=None, status="거래중", listed_at=date.today()),
        ]
        db.add_all(rows)
        db.commit()
        for r in rows:
            db.refresh(r)
        tx_ids = [r.id for r in rows]

        status_resp = admin_service.get_data_status(db)

        region_entry = next(r for r in status_resp.region_counts if r.region_name == "관리자검증동")
        assert region_entry.normal_count == 2 and region_entry.error_count == 0 and region_entry.error_rate == 0.0

        unmatched_entry = next(r for r in status_resp.region_counts if r.region_name == "지역 매칭 실패")
        assert unmatched_entry.error_count >= 2  # 다른 테스트/실데이터의 매칭 실패 건도 섞여 있을 수 있음

        vacuum_entry = next(c for c in status_resp.category_counts if c.category == "청소기")
        assert vacuum_entry.normal_count >= 2 and vacuum_entry.error_count >= 1
        assert 0 < vacuum_entry.error_rate < 1

        clothes_entry = next(c for c in status_resp.category_counts if c.category == "의류")
        assert clothes_entry.error_count >= 1 and clothes_entry.error_rate > 0

        assert any("매칭실패 청소기" in e.message for e in status_resp.recent_errors)

        # require_admin 게이트 — 일반 유저는 403, 관리자는 200.
        try:
            require_admin(user=normal_user)
            raise AssertionError("일반 유저가 admin 게이트를 통과하면 안 된다")
        except HTTPException as e:
            assert e.status_code == 403
        assert require_admin(user=admin_user).id == admin_user.id

        client = TestClient(app)
        from app.core.security import create_access_token

        admin_token = create_access_token(subject=str(admin_user.id), role="admin")
        user_token = create_access_token(subject=str(normal_user.id), role="user")

        forbidden = client.get("/api/v1/admin/data-status", headers={"Authorization": f"Bearer {user_token}"})
        assert forbidden.status_code == 403

        ok = client.get("/api/v1/admin/data-status", headers={"Authorization": f"Bearer {admin_token}"})
        assert ok.status_code == 200
        assert "region_counts" in ok.json() and "category_counts" in ok.json()

        print("admin data-status self-check OK")
    finally:
        db.query(Transaction).filter(Transaction.id.in_(tx_ids)).delete(synchronize_session=False)
        db.delete(admin_user)
        db.delete(normal_user)
        db.delete(region)
        db.commit()
        db.close()


if __name__ == "__main__":
    main()
