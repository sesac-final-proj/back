import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.v1.support.router import router
from app.core.db import Base, get_db
from app.core.exceptions import register_exception_handlers
from app.core.security import create_access_token
from app.models.support import SupportInquiry, SupportInquiryMessage
from app.models.user import User, UserRole


@pytest.fixture
def support_api():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine, tables=[User.__table__, SupportInquiry.__table__, SupportInquiryMessage.__table__])
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(router)
    with Session(engine) as db:
        def session():
            yield db
        app.dependency_overrides[get_db] = session
        user = User(email="user@example.com", nickname="사용자", role=UserRole.USER)
        other = User(email="other@example.com", nickname="다른사용자", role=UserRole.USER)
        admin = User(email="admin@example.com", nickname="관리자", role=UserRole.ADMIN)
        db.add_all([user, other, admin]); db.commit()
        headers = lambda row, role: {"Authorization": "Bearer " + create_access_token(str(row.id), role=role)}
        yield TestClient(app), headers(user, "user"), headers(other, "user"), headers(admin, "admin")
    engine.dispose()


def test_inquiry_lifecycle_and_access(support_api):
    client, user_headers, other_headers, admin_headers = support_api
    created = client.post("/api/v1/support/inquiries", headers=user_headers, json={"title": "결제 문의", "content": "결제가 처리되지 않았어요."})
    assert created.status_code == 201
    inquiry_id = created.json()["id"]
    assert created.json()["status"] == "WAITING"
    assert client.get("/api/v1/support/inquiries", headers=other_headers).json()["total"] == 0
    assert client.get("/api/v1/support/admin/inquiries", headers=user_headers).status_code == 403
    answered = client.put(f"/api/v1/support/admin/inquiries/{inquiry_id}/answer", headers=admin_headers, json={"answer": "결제 상태를 복구했습니다."})
    assert answered.status_code == 200 and answered.json()["status"] == "ANSWERED"
    follow_up = client.post(f"/api/v1/support/inquiries/{inquiry_id}/messages", headers=user_headers, json={"content": "추가로 영수증도 확인해주세요."})
    assert follow_up.status_code == 200 and follow_up.json()["status"] == "WAITING"
    assert len(follow_up.json()["messages"]) == 3
    assert client.post(f"/api/v1/support/inquiries/{inquiry_id}/messages", headers=other_headers, json={"content": "남의 문의"}).status_code == 404
    closed = client.post(f"/api/v1/support/admin/inquiries/{inquiry_id}/close", headers=admin_headers)
    assert closed.status_code == 200 and closed.json()["status"] == "CLOSED"
    assert client.put(f"/api/v1/support/admin/inquiries/{inquiry_id}/answer", headers=admin_headers, json={"answer": "추가 답변"}).status_code == 400
    assert client.post(f"/api/v1/support/inquiries/{inquiry_id}/messages", headers=user_headers, json={"content": "종료 후 질문"}).status_code == 400


def test_only_admin_can_close_inquiry(support_api):
    client, user_headers, _, admin_headers = support_api
    inquiry_id = client.post("/api/v1/support/inquiries", headers=user_headers, json={"title": "기타 문의", "content": "답변을 기다립니다."}).json()["id"]
    assert client.post(f"/api/v1/support/admin/inquiries/{inquiry_id}/close", headers=user_headers).status_code == 403
    assert client.post(f"/api/v1/support/admin/inquiries/{inquiry_id}/close", headers=admin_headers).status_code == 200
