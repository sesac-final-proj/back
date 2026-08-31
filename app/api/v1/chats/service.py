from sqlalchemy.orm import Session

from app.api.v1.chats import schema
from app.core.exceptions import AppError, NotFoundError
from app.models.chat import ChatRoom, ChatRoomParticipant
from app.models.product import Product
from app.models.user import User


def create_chat_room(db: Session, user: User, data: schema.ChatRoomCreateRequest) -> schema.ChatRoomResponse:
    if data.type != "TRADE":
        # COMMUNITY/GROUP/SYSTEM 채팅방은 이 이슈(10-marketplace-core) 범위 밖.
        raise AppError("TRADE 타입 채팅방만 아직 지원합니다.")

    product = db.get(Product, data.product_id)
    if product is None:
        raise NotFoundError("상품을 찾을 수 없습니다.")

    room = ChatRoom(type=data.type, title=product.title, product_id=product.id, verified=False)
    db.add(room)
    db.flush()  # room.id 확보

    db.add(ChatRoomParticipant(chat_room_id=room.id, user_id=user.id, unread_count=0))
    db.commit()
    db.refresh(room)

    return schema.ChatRoomResponse(
        id=room.id,
        type=room.type,
        title=room.title,
        last_message=room.last_message,
        last_message_at=room.last_message_at,
        unread_count=0,
        verified=room.verified,
    )


def list_my_chat_rooms(db: Session, user: User, page: int, size: int) -> schema.ChatRoomListResponse:
    query = (
        db.query(ChatRoom, ChatRoomParticipant.unread_count)
        .join(ChatRoomParticipant, ChatRoomParticipant.chat_room_id == ChatRoom.id)
        .filter(ChatRoomParticipant.user_id == user.id)
    )
    total = query.count()
    rows = (
        query.order_by(ChatRoom.last_message_at.desc(), ChatRoom.created_at.desc())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )
    items = [
        schema.ChatRoomResponse(
            id=room.id,
            type=room.type,
            title=room.title,
            last_message=room.last_message,
            last_message_at=room.last_message_at,
            unread_count=unread_count,
            verified=room.verified,
        )
        for room, unread_count in rows
    ]
    return schema.ChatRoomListResponse(items=items, total=total)
