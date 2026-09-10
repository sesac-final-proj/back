from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.v1.notices import schema, service
from app.core.db import get_db

router = APIRouter(prefix="/api/v1/notices", tags=["공지사항"])


@router.get("", response_model=schema.NoticeListResponse)
def list_notices(
    service_param: str | None = Query(default=None, alias="service"),
    service_type: str | None = Query(default=None, alias="service_type"),
    db: Session = Depends(get_db),
):
    target_service = service_param or service_type
    return service.get_published_notices(db, service=target_service)


@router.get("/{notice_id}", response_model=schema.NoticeItem)
def get_notice(
    notice_id: int,
    db: Session = Depends(get_db),
):
    return service.get_published_notice_by_id(db, notice_id=notice_id)
