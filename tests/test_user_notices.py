from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.v1.notices.router import router as notices_router
from app.core.db import Base, get_db
from app.models.notice import AdminNotice
from app.models.user import User, UserRole


@pytest.fixture
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine, tables=[User.__table__, AdminNotice.__table__])
    app = FastAPI()
    app.include_router(notices_router)
    with Session(engine) as db:
        now = datetime.now(timezone.utc)

        # 1. 게시중인 꿈가지 공지
        notice_dream = AdminNotice(
            service="dream",
            title="꿈가지 오픈",
            content="꿈가지 내용",
            starts_at=now - timedelta(days=1),
            ends_at=now + timedelta(days=5),
            display_order=1,
        )
        # 2. 게시중인 당근 공지
        notice_carrot = AdminNotice(
            service="carrot",
            title="당근 공지",
            content="당근 내용",
            starts_at=now - timedelta(days=1),
            ends_at=None,
            display_order=2,
        )
        # 3. 예약 공지 (starts_at 미래)
        notice_scheduled = AdminNotice(
            service="dream",
            title="미래 공지",
            content="미래",
            starts_at=now + timedelta(days=2),
        )
        # 4. 종료된 공지 (ends_at 과거)
        notice_ended = AdminNotice(
            service="dream",
            title="종료 공지",
            content="종료",
            starts_at=now - timedelta(days=10),
            ends_at=now - timedelta(days=1),
        )
        # 5. 숨김 공지 (manual_status=hidden)
        notice_hidden = AdminNotice(
            service="dream",
            title="숨김 공지",
            content="숨김",
            manual_status="hidden",
            starts_at=now - timedelta(days=1),
        )
        # 6. 삭제된 공지
        notice_deleted = AdminNotice(
            service="dream",
            title="삭제 공지",
            content="삭제",
            starts_at=now - timedelta(days=1),
            deleted_at=now,
        )

        db.add_all([notice_dream, notice_carrot, notice_scheduled, notice_ended, notice_hidden, notice_deleted])
        db.commit()

        def session():
            yield db

        app.dependency_overrides[get_db] = session
        yield TestClient(app), notice_dream.id, notice_carrot.id
    engine.dispose()


def test_user_notices_filtering(client):
    test_client, dream_id, carrot_id = client

    # Dream 공지만 조회
    res_dream = test_client.get("/api/v1/notices?service=dream")
    assert res_dream.status_code == 200
    data_dream = res_dream.json()
    assert data_dream["total"] == 1
    assert data_dream["items"][0]["id"] == dream_id
    assert data_dream["items"][0]["title"] == "꿈가지 오픈"

    # Carrot 공지만 조회
    res_carrot = test_client.get("/api/v1/notices?service=carrot")
    assert res_carrot.status_code == 200
    data_carrot = res_carrot.json()
    assert data_carrot["total"] == 1
    assert data_carrot["items"][0]["id"] == carrot_id
    assert data_carrot["items"][0]["title"] == "당근 공지"

    # 전체 조회
    res_all = test_client.get("/api/v1/notices")
    assert res_all.status_code == 200
    assert res_all.json()["total"] == 2

    # 단건 상세 조회
    res_detail = test_client.get(f"/api/v1/notices/{dream_id}")
    assert res_detail.status_code == 200
    assert res_detail.json()["title"] == "꿈가지 오픈"

    # 존재하지 않거나 비공개 공지 상세 조회 시 404
    res_not_found = test_client.get("/api/v1/notices/9999")
    assert res_not_found.status_code == 404
