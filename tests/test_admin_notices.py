from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.v1.admin.router import router as admin_router
from app.core.db import Base, get_db
from app.core.security import create_access_token
from app.models.notice import AdminNotice, AdminNoticeAlert
from app.models.user import User, UserRole


@pytest.fixture
def portal():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine, tables=[User.__table__, AdminNotice.__table__, AdminNoticeAlert.__table__])
    app = FastAPI()
    app.include_router(admin_router)
    with Session(engine) as db:
        admin = User(email="notice-admin@example.com", nickname="notice-admin", role=UserRole.ADMIN)
        user = User(email="notice-user@example.com", nickname="notice-user", role=UserRole.USER)
        db.add_all([admin, user])
        db.commit()
        db.refresh(admin)

        def session():
            yield db

        app.dependency_overrides[get_db] = session
        headers = {"Authorization": "Bearer " + create_access_token(str(admin.id), role="admin")}
        yield db, TestClient(app), headers
    engine.dispose()


def test_notice_filters_soft_delete_duplicate_alerts_and_order(portal):
    db, client, headers = portal
    now = datetime.now(timezone.utc)
    first = client.post(
        "/api/v1/admin/notices",
        headers=headers,
        json={"service": "dream", "title": "꿈가지 공지", "content": "후원 시작", "starts_at": now.isoformat()},
    )
    assert first.status_code == 201
    second = client.post(
        "/api/v1/admin/notices",
        headers=headers,
        json={"service": "carrot", "title": "당근 점검", "content": "검색 대상", "starts_at": (now + timedelta(days=1)).isoformat()},
    )
    assert second.status_code == 201

    filtered = client.get("/api/v1/admin/notices?q=검색&service=carrot&status=scheduled&page=1&size=10", headers=headers)
    assert filtered.status_code == 200
    assert filtered.json()["total"] == 1

    alert = client.post(f"/api/v1/admin/notices/{first.json()['id']}/alerts", headers=headers)
    assert alert.status_code == 200
    assert alert.json()["created_count"] == 1
    duplicate_alert = client.post(f"/api/v1/admin/notices/{first.json()['id']}/alerts", headers=headers)
    assert duplicate_alert.json()["created_count"] == 0
    assert duplicate_alert.json()["alert_count"] == 1

    copied = client.post(f"/api/v1/admin/notices/{first.json()['id']}/duplicate", headers=headers)
    assert copied.status_code == 201
    copied_body = copied.json()
    assert copied_body["status"] == "draft"
    assert copied_body["starts_at"] is None
    assert copied_body["ends_at"] is None
    assert copied_body["alert_count"] == 0

    order = client.patch("/api/v1/admin/notices/order", headers=headers, json={"notice_ids": [second.json()["id"], first.json()["id"], copied_body["id"]]})
    assert order.status_code == 200
    assert order.json()["items"][0]["id"] == second.json()["id"]

    deleted = client.delete(f"/api/v1/admin/notices/{first.json()['id']}", headers=headers)
    assert deleted.status_code == 204
    listed = client.get("/api/v1/admin/notices", headers=headers)
    ids = [item["id"] for item in listed.json()["items"]]
    assert first.json()["id"] not in ids
    assert db.get(AdminNotice, first.json()["id"]).deleted_at is not None
