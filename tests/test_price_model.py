"""가격예측 모델 대시보드(app/api/v1/admin price-model 엔드포인트) 자가 점검.

python -m tests.test_price_model 로 실행. scripts/seed_price_model_data.py로 이미
적재된 실 데이터를 전제로 한다(비어 있어도 빈 응답으로 통과는 하지만, 의미 있는
검증을 하려면 먼저 그 스크립트를 한 번 돌려두는 게 좋다).
"""
from fastapi.testclient import TestClient

from app.api.v1.admin import service as admin_service
from app.core.db import SessionLocal
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models.user import User, UserRole


def main():
    db = SessionLocal()
    admin = User(
        email="__price_model_selfcheck_admin__@example.com",
        password_hash=hash_password("x"),
        nickname="pm_admin_sc",
        role=UserRole.ADMIN,
    )
    normal_user = User(
        email="__price_model_selfcheck_user__@example.com",
        password_hash=hash_password("x"),
        nickname="pm_user_sc",
        role=UserRole.USER,
    )
    db.add_all([admin, normal_user])
    db.commit()
    db.refresh(admin)
    db.refresh(normal_user)

    try:
        metrics = admin_service.get_price_model_metrics(db)
        # feature_set(full/no_leak_prone) x model_key(random_forest/lightgbm) = 4건 고정.
        assert len(metrics.metrics) == 4
        for m in metrics.metrics:
            assert m.feature_set in ("full", "no_leak_prone")
            assert 0 <= m.r2 <= 1

        listings = admin_service.list_price_model_listings(db, None, None, page=1, size=5)
        assert listings.total > 0
        assert len(listings.items) == 5

        filtered = admin_service.list_price_model_listings(db, "청소기", None, page=1, size=1)
        assert filtered.total > 0
        assert all(
            item.category == "청소기"
            for item in admin_service.list_price_model_listings(db, "청소기", None, page=1, size=filtered.total).items
        )

        distribution = admin_service.get_price_distribution(db, "청소기", sample=30)
        assert len(distribution.categories) == 1
        cat = distribution.categories[0]
        assert cat.category == "청소기"
        assert len(cat.points) <= 30
        # 세부유형 상위 5개 + "기타" 묶음 — 그 이상 개별 이름이 남아있으면 안 된다.
        assert len(cat.types) <= admin_service.PRICE_DISTRIBUTION_TOP_TYPES + 1

        empty = admin_service.get_price_distribution(db, "존재하지않는카테고리", sample=10)
        assert empty.categories == []

        charts = admin_service.get_price_model_charts(db)
        assert len(charts.predictions) > 0
        assert len(charts.platform_comparisons) > 0
        assert len(charts.platform_tests) > 0
        assert len(charts.clusters) > 0
        assert len(charts.feature_importance) > 0
        assert {f.feature_set for f in charts.feature_importance} == {"full", "no_leak_prone"}
        # gain 내림차순 정렬(피처세트별) — Chart.js horizontal bar가 바로 쓸 수 있게.
        full_gains = [f.gain for f in charts.feature_importance if f.feature_set == "full"]
        assert full_gains == sorted(full_gains, reverse=True)

        # HTTP 레벨 — require_admin 게이트(일반 유저 403, 관리자 200) + 스키마 대략 확인.
        client = TestClient(app)
        admin_token = create_access_token(subject=str(admin.id), role="admin")
        user_token = create_access_token(subject=str(normal_user.id), role="user")

        forbidden = client.get(
            "/api/v1/admin/price-model/metrics", headers={"Authorization": f"Bearer {user_token}"}
        )
        assert forbidden.status_code == 403

        ok = client.get(
            "/api/v1/admin/price-model/listings?page=1&size=2",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert ok.status_code == 200
        assert "items" in ok.json() and "total" in ok.json()

        print("price-model self-check OK")
    finally:
        db.delete(admin)
        db.delete(normal_user)
        db.commit()
        db.close()


if __name__ == "__main__":
    main()
