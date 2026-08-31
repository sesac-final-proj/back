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
    page: int = 1,
    size: int = 20,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return service.list_my_chat_rooms(db, user, page, size)


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
