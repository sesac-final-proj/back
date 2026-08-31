from sqlalchemy.orm import Session

from app.api.v1.chats import schema
from app.core.exceptions import AppError, NotFoundError, PermissionDeniedError
from app.models.chat import ChatMessage, ChatRoom, ChatRoomParticipant
from app.models.product import Product
from app.models.user import User


def _get_participant(db: Session, chat_room_id: int, user_id: int) -> ChatRoomParticipant | None:
    return (
        db.query(ChatRoomParticipant)
        .filter(ChatRoomParticipant.chat_room_id == chat_room_id, ChatRoomParticipant.user_id == user_id)
        .first()
    )


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


def send_message(
    db: Session, user: User, chat_room_id: int, data: schema.MessageCreateRequest
) -> schema.MessageResponse:
    room = db.get(ChatRoom, chat_room_id)
    if room is None:
        raise NotFoundError("채팅방을 찾을 수 없습니다.")
    if _get_participant(db, chat_room_id, user.id) is None:
        raise PermissionDeniedError("참여자만 메시지를 보낼 수 있습니다.")

    message = ChatMessage(chat_room_id=chat_room_id, sender_id=user.id, content=data.content)
    db.add(message)
    db.flush()  # message.created_at 확보

    room.last_message = message.content
    room.last_message_at = message.created_at

    # 실시간 push는 범위 밖(REST 폴링 전제) — 발신자를 제외한 참여자의 안읽음만 증가.
    db.query(ChatRoomParticipant).filter(
        ChatRoomParticipant.chat_room_id == chat_room_id,
        ChatRoomParticipant.user_id != user.id,
    ).update({ChatRoomParticipant.unread_count: ChatRoomParticipant.unread_count + 1})

    db.commit()
    db.refresh(message)
    return schema.MessageResponse.model_validate(message)


def list_messages(db: Session, user: User, chat_room_id: int, page: int, size: int) -> schema.MessageListResponse:
    participant = _get_participant(db, chat_room_id, user.id)
    if participant is None:
        if db.get(ChatRoom, chat_room_id) is None:
            raise NotFoundError("채팅방을 찾을 수 없습니다.")
        raise PermissionDeniedError("참여자만 조회할 수 있습니다.")

    query = db.query(ChatMessage).filter(ChatMessage.chat_room_id == chat_room_id)
    total = query.count()
    rows = (
        query.order_by(ChatMessage.created_at.asc())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )

    participant.unread_count = 0
    db.commit()

    items = [schema.MessageResponse.model_validate(m) for m in rows]
    return schema.MessageListResponse(items=items, total=total)
