from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.v1.notices import schema
from app.models.notice import AdminNotice


def get_published_notices(db: Session, service: str | None = None) -> schema.NoticeListResponse:
    now = datetime.now(timezone.utc)
    query = db.query(AdminNotice).filter(
        AdminNotice.deleted_at.is_(None),
        or_(AdminNotice.manual_status.is_(None), AdminNotice.manual_status != "hidden"),
        AdminNotice.starts_at.is_not(None),
        AdminNotice.starts_at <= now,
        or_(AdminNotice.ends_at.is_(None), AdminNotice.ends_at >= now),
    )
    if service in ("dream", "carrot"):
        query = query.filter(AdminNotice.service == service)

    rows = query.order_by(AdminNotice.display_order.asc(), AdminNotice.created_at.desc(), AdminNotice.id.desc()).all()
    items = [schema.NoticeItem.model_validate(row) for row in rows]
    return schema.NoticeListResponse(items=items, total=len(items))


def get_published_notice_by_id(db: Session, notice_id: int) -> schema.NoticeItem:
    now = datetime.now(timezone.utc)
    notice = db.query(AdminNotice).filter(
        AdminNotice.id == notice_id,
        AdminNotice.deleted_at.is_(None),
        or_(AdminNotice.manual_status.is_(None), AdminNotice.manual_status != "hidden"),
        AdminNotice.starts_at.is_not(None),
        AdminNotice.starts_at <= now,
        or_(AdminNotice.ends_at.is_(None), AdminNotice.ends_at >= now),
    ).first()
    if notice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="공지를 찾을 수 없습니다.")
    return schema.NoticeItem.model_validate(notice)
