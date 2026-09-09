from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.v1.admin.router import router as admin_router
from app.api.v1.admin.service import get_dashboard_overview
from app.api.v1.auth import service as auth_service
from app.api.v1.auth.router import router as auth_router
from app.core.db import Base, get_db
from app.core.security import create_access_token, hash_password
from app.models.region import Region
from app.models.transaction import Transaction
from app.models.user import User, UserRole


@pytest.fixture
def portal(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine, tables=[Region.__table__, User.__table__, Transaction.__table__])
    tokens = set()
    monkeypatch.setattr(auth_service, "save_refresh_token", lambda jti, *_: tokens.add(jti))
    monkeypatch.setattr(auth_service, "is_refresh_token_valid", lambda jti: jti in tokens)
    monkeypatch.setattr(auth_service, "revoke_refresh_token", lambda jti: tokens.discard(jti))
    app = FastAPI()
    app.include_router(admin_router)
    app.include_router(auth_router)
    with Session(engine) as db:
        def session():
            yield db
        app.dependency_overrides[get_db] = session
        yield db, TestClient(app)
    engine.dispose()


def test_overview_empty_and_date_window(portal):
    db, _ = portal
    empty = get_dashboard_overview(db)
    assert empty.summary.total_transactions == 0
    assert empty.summary.average_listing_price is None
    assert empty.summary.price_eligible_rate == 0
    assert empty.source.status == "empty"
    assert len(empty.collection_trend) == 14
    today = datetime.now(timezone.utc).date()
    region = Region(dong_code="test", dong_name="문정동", gu_name="송파구", lat=0, lng=0)
    db.add(region)
    db.flush()
    for age, price, region_id in [(0, 100, region.id), (13, 0, region.id), (14, None, None)]:
        db.add(Transaction(product_title="집계 검증", category="가전", price=price, region_id=region_id,
                           status="판매중", listed_at=date.today(),
                           collected_at=datetime.combine(today - timedelta(days=age), datetime.min.time())))
    db.commit()
    result = get_dashboard_overview(db)
    assert result.summary.total_transactions == 3
    assert result.summary.price_eligible_transactions == 2
    assert result.summary.price_eligible_rate == 66.7
    assert result.summary.average_listing_price == 50
    assert result.summary.active_regions == 1
    assert sum(row.transaction_count for row in result.collection_trend) == 2
    assert result.collection_trend[0].date == today - timedelta(days=13)
    assert result.collection_trend[-1].date == today
    assert result.region_ranking[0].region_name == "송파구 문정동"
    assert len(result.recent_transactions) == 3


def test_admin_auth_and_overview_contract(portal):
    db, client = portal
    admin = User(email="portal-admin@example.com", nickname="운영자", role=UserRole.ADMIN, password_hash=hash_password("test-password-123"))
    normal = User(email="portal-user@example.com", nickname="일반", role=UserRole.USER)
    db.add_all([admin, normal])
    db.commit()
    url = "/api/v1/admin/dashboard/overview"
    assert client.get(url).status_code == 401
    normal_headers = {"Authorization": "Bearer " + create_access_token(str(normal.id), role="user")}
    for path in [url, "/api/v1/admin/data-status", "/api/v1/admin/audience-insights", "/api/v1/admin/dream-status"]:
        assert client.get(path, headers=normal_headers).status_code == 403
    assert client.post("/api/v1/auth/admin/login", json={"email": admin.email, "password": "wrong"}).status_code == 401
    login = client.post("/api/v1/auth/admin/login", json={"email": admin.email, "password": "test-password-123"})
    assert login.status_code == 200
    pair = login.json()
    headers = {"Authorization": "Bearer " + pair["access_token"]}
    me = client.get("/api/v1/auth/admin/me", headers=headers)
    assert me.status_code == 200 and me.json()["role"] == "admin"
    assert "password_hash" not in me.json()
    assert client.get(url + "?range=14d", headers=headers).status_code == 200
    assert client.get(url + "?range=30d", headers=headers).status_code == 422
    assert client.post("/api/v1/auth/admin/password", headers=headers, json={"current_password": "wrong", "new_password": "new-password-123"}).status_code == 401
    assert client.post("/api/v1/auth/admin/password", headers=headers, json={"current_password": "test-password-123", "new_password": "new-password-123"}).status_code == 200
    assert client.post("/api/v1/auth/admin/login", json={"email": admin.email, "password": "new-password-123"}).status_code == 200
    refresh = client.post("/api/v1/auth/admin/refresh", json={"refresh_token": pair["refresh_token"]})
    assert refresh.status_code == 200
    assert client.post("/api/v1/auth/admin/refresh", json={"refresh_token": pair["refresh_token"]}).status_code == 401
    rotated = refresh.json()["refresh_token"]
    assert client.post("/api/v1/auth/admin/logout", json={"refresh_token": rotated}).status_code == 200
    assert client.post("/api/v1/auth/admin/refresh", json={"refresh_token": rotated}).status_code == 401
