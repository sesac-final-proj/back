from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.v1.safety import schema, service
from app.core.db import get_db
from app.core.deps import get_current_user
from app.models.user import User

router = APIRouter(prefix="/api/v1/safety", tags=["안전(차단/신고)"])


@router.post("/blocks/{target_user_id}", response_model=schema.BlockResponse)
def block_user(
    target_user_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return service.block_user(db, user, target_user_id)


@router.delete("/blocks/{target_user_id}", response_model=schema.BlockResponse)
def unblock_user(
    target_user_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return service.unblock_user(db, user, target_user_id)


@router.get("/blocks", response_model=schema.BlockedUserListResponse)
def list_my_blocks(
    page: int = 1,
    size: int = 20,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return service.list_my_blocks(db, user, page, size)


@router.post("/reports", response_model=schema.ReportCreated, status_code=status.HTTP_201_CREATED)
def create_report(
    body: schema.ReportCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    report = service.create_report(db, user, body)
    return schema.ReportCreated(id=report.id)
