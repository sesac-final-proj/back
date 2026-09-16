from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.api.v1.support import schema, service
from app.core.db import get_db
from app.core.deps import get_current_user, require_admin
from app.models.user import User
from app.models.support import SupportInquiryStatus

router = APIRouter(prefix="/api/v1/support", tags=["고객센터"])


@router.post("/inquiries", response_model=schema.InquiryResponse, status_code=status.HTTP_201_CREATED)
def create_inquiry(body: schema.InquiryCreateRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return service.create_inquiry(db, user, body)


@router.get("/inquiries", response_model=schema.InquiryListResponse)
def my_inquiries(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return service.list_my_inquiries(db, user)


@router.post("/inquiries/{inquiry_id}/messages", response_model=schema.InquiryResponse)
def add_user_message(body: schema.InquiryMessageRequest, inquiry_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return service.add_user_message(db, user, inquiry_id, body)


@router.get("/admin/inquiries", response_model=schema.InquiryListResponse)
def admin_inquiries(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return service.list_all_inquiries(db)


@router.put("/admin/inquiries/{inquiry_id}/answer", response_model=schema.InquiryResponse)
def answer_inquiry(body: schema.InquiryAnswerRequest, inquiry_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return service.answer_inquiry(db, admin, inquiry_id, body)


@router.get("/admin/inquiry-page", response_model=schema.InquiryPage)
def inquiry_page(page: int = Query(1, ge=1), page_size: int = Query(15, ge=1, le=100),
                 status: SupportInquiryStatus | None = None, search: str = Query("", max_length=120),
                 admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return service.list_inquiry_page(db, page, page_size, status, search)


@router.get("/admin/inquiries/{inquiry_id}", response_model=schema.InquiryResponse)
def inquiry_detail(inquiry_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return service.get_admin_inquiry(db, inquiry_id)


@router.post("/admin/inquiries/{inquiry_id}/close", response_model=schema.InquiryResponse)
def close_inquiry(inquiry_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return service.close_inquiry(db, admin, inquiry_id)


@router.delete("/admin/inquiries/{inquiry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_inquiry(inquiry_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    service.delete_closed_inquiry(db, inquiry_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
