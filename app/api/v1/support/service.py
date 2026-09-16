from datetime import datetime, timezone

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.v1.support import schema
from app.core.exceptions import AppError, NotFoundError
from app.models.support import SupportInquiry, SupportInquiryMessage, SupportInquiryStatus
from app.models.user import User


def _response(row: SupportInquiry, include_user: bool = False) -> schema.InquiryResponse:
    messages = [schema.InquiryMessageResponse(id=message.id, author_role=message.author_role, content=message.content, created_at=message.created_at) for message in row.messages]
    if not messages:
        messages.append(schema.InquiryMessageResponse(author_role="USER", content=row.content, created_at=row.created_at))
        if row.answer and row.answered_at:
            messages.append(schema.InquiryMessageResponse(author_role="ADMIN", content=row.answer, created_at=row.answered_at))
    return schema.InquiryResponse(
        id=row.id,
        user_id=row.user_id,
        title=row.title,
        content=row.content,
        status=row.status.value if hasattr(row.status, "value") else row.status,
        answer=row.answer,
        answered_at=row.answered_at,
        closed_at=row.closed_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
        user_nickname=row.user.nickname if include_user and row.user else None,
        user_email=row.user.email if include_user and row.user else None,
        messages=messages,
    )


def create_inquiry(db: Session, user: User, data: schema.InquiryCreateRequest) -> schema.InquiryResponse:
    row = SupportInquiry(user_id=user.id, title=data.title.strip(), content=data.content.strip())
    db.add(row)
    db.flush()
    db.add(SupportInquiryMessage(inquiry_id=row.id, author_id=user.id, author_role="USER", content=data.content.strip()))
    db.commit()
    db.refresh(row)
    return _response(row)


def list_my_inquiries(db: Session, user: User) -> schema.InquiryListResponse:
    rows = db.query(SupportInquiry).filter(SupportInquiry.user_id == user.id).order_by(SupportInquiry.created_at.desc()).all()
    return schema.InquiryListResponse(items=[_response(row) for row in rows], total=len(rows))


def add_user_message(db: Session, user: User, inquiry_id: int, data: schema.InquiryMessageRequest) -> schema.InquiryResponse:
    row = db.get(SupportInquiry, inquiry_id)
    if row is None or row.user_id != user.id:
        raise NotFoundError("문의를 찾을 수 없습니다.")
    if row.status == SupportInquiryStatus.CLOSED:
        raise AppError("종료된 문의에는 추가 질문을 남길 수 없습니다.")
    db.add(SupportInquiryMessage(inquiry_id=row.id, author_id=user.id, author_role="USER", content=data.content.strip()))
    row.status = SupportInquiryStatus.WAITING
    db.commit()
    db.refresh(row)
    return _response(row)


def list_all_inquiries(db: Session) -> schema.InquiryListResponse:
    rows = db.query(SupportInquiry).order_by(SupportInquiry.created_at.desc()).all()
    return schema.InquiryListResponse(items=[_response(row, include_user=True) for row in rows], total=len(rows))


def list_inquiry_page(db: Session, page: int, page_size: int, status: SupportInquiryStatus | None, search: str) -> schema.InquiryPage:
    query = db.query(SupportInquiry.id, SupportInquiry.title, SupportInquiry.status,
                     SupportInquiry.created_at, User.nickname.label("user_nickname"),
                     User.email.label("user_email")).outerjoin(User, User.id == SupportInquiry.user_id)
    if status is not None:
        query = query.filter(SupportInquiry.status == status)
    if search.strip():
        term = search.strip()
        query = query.filter(or_(SupportInquiry.title.contains(term, autoescape=True),
                                 User.nickname.contains(term, autoescape=True),
                                 User.email.contains(term, autoescape=True)))
    total = query.count()
    page = min(page, max(1, (total + page_size - 1) // page_size))
    rows = query.order_by(SupportInquiry.created_at.desc(), SupportInquiry.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return schema.InquiryPage(items=[schema.InquirySummary(**row._mapping) for row in rows],
                              total=total, page=page, page_size=page_size)


def get_admin_inquiry(db: Session, inquiry_id: int) -> schema.InquiryResponse:
    row = db.get(SupportInquiry, inquiry_id)
    if row is None:
        raise NotFoundError("문의를 찾을 수 없습니다.")
    return _response(row, include_user=True)


def answer_inquiry(db: Session, admin: User, inquiry_id: int, data: schema.InquiryAnswerRequest) -> schema.InquiryResponse:
    row = db.get(SupportInquiry, inquiry_id)
    if row is None:
        raise NotFoundError("문의를 찾을 수 없습니다.")
    if row.status == SupportInquiryStatus.CLOSED:
        raise AppError("종료된 문의에는 답변할 수 없습니다.")
    row.answer = data.answer.strip()
    db.add(SupportInquiryMessage(inquiry_id=row.id, author_id=admin.id, author_role="ADMIN", content=data.answer.strip()))
    row.answered_by_id = admin.id
    row.answered_at = datetime.now(timezone.utc)
    row.status = SupportInquiryStatus.ANSWERED
    db.commit()
    db.refresh(row)
    return _response(row, include_user=True)


def close_inquiry(db: Session, admin: User, inquiry_id: int) -> schema.InquiryResponse:
    row = db.get(SupportInquiry, inquiry_id)
    if row is None:
        raise NotFoundError("문의를 찾을 수 없습니다.")
    if row.status == SupportInquiryStatus.CLOSED:
        raise AppError("이미 종료된 문의입니다.")
    row.status = SupportInquiryStatus.CLOSED
    row.closed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    return _response(row, include_user=True)


def delete_closed_inquiry(db: Session, inquiry_id: int) -> None:
    row = db.query(SupportInquiry).filter(SupportInquiry.id == inquiry_id).with_for_update().first()
    if row is None:
        raise NotFoundError("문의를 찾을 수 없습니다.")
    if row.status != SupportInquiryStatus.CLOSED:
        raise AppError("종료된 문의만 삭제할 수 있습니다.")
    db.delete(row)
    db.commit()
