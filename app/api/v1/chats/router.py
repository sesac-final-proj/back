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
