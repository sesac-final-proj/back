from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.v1.chats import schema, service
from app.core.db import get_db
from app.core.deps import get_current_user
from app.models.user import User

router = APIRouter(prefix="/api/v1/chats", tags=["채팅"])


@router.post("", response_model=schema.ChatRoomResponse, status_code=status.HTTP_201_CREATED)
def create_chat_room(
    body: schema.ChatRoomCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return service.create_chat_room(db, user, body)


@router.get("", response_model=schema.ChatRoomListResponse)
def list_chat_rooms(
    product_id: int | None = None,
    page: int = 1,
    size: int = 20,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # product_id를 주면 판매자가 자기 상품에 걸린 채팅방들을 N:1로 조회하는 용도.
    return service.list_my_chat_rooms(db, user, page, size, product_id)


@router.post("/{chat_room_id}/images/presign", response_model=schema.ImagePresignResponse)
def presign_chat_image(
    chat_room_id: int,
    body: schema.ImagePresignRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return service.presign_chat_image(db, user, chat_room_id, body)


@router.post(
    "/{chat_room_id}/messages",
    response_model=schema.MessageResponse,
    status_code=status.HTTP_201_CREATED,
)
def send_message(
    chat_room_id: int,
    body: schema.MessageCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return service.send_message(db, user, chat_room_id, body)


@router.get("/{chat_room_id}/messages", response_model=schema.MessageListResponse)
def list_messages(
    chat_room_id: int,
    page: int = 1,
    size: int = 20,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return service.list_messages(db, user, chat_room_id, page, size)


@router.delete("/{chat_room_id}", status_code=status.HTTP_204_NO_CONTENT)
def leave_chat_room(
    chat_room_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service.leave_chat_room(db, user, chat_room_id)


@router.patch("/{chat_room_id}/status", response_model=schema.MessageResponse)
def update_chat_trade_status(
    chat_room_id: int,
    body: schema.ChatRoomStatusUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return service.update_trade_status(db, user, chat_room_id, body)
