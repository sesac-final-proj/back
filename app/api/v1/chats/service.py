from sqlalchemy.orm import Session

from app.api.v1.chats import schema
from app.api.v1.safety import service as safety_service
from app.api.v1.trades import service as trade_service
from app.core import storage
from app.core.exceptions import AppError, NotFoundError, PermissionDeniedError
from app.models.chat import ChatMessage, ChatRoom, ChatRoomParticipant
from app.models.product import Product
from app.models.region import Region
from app.models.user import User

_STATUS_MESSAGES = {
    "SALE": "판매중으로 변경했어요",
    "RESERVED": "예약중으로 변경했어요",
    "SOLD": "거래가 완료되었어요",
}


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
    if product.created_by == user.id:
        raise AppError("본인 상품에는 채팅을 걸 수 없습니다.")
    if product.created_by is not None and safety_service.is_blocked(db, user.id, product.created_by):
        raise PermissionDeniedError("차단 관계에서는 채팅을 시작할 수 없습니다.")

    # 여기 도달하면 항상 구매자다 (본인 상품이면 위에서 이미 막힘) -> is_seller=False 고정.
    existing = _find_existing_trade_room(db, product.id, user.id)
    if existing is not None:
        counterpart = _counterparts_by_room(db, [existing.id], user.id).get(existing.id)
        return _to_response(
            existing, existing_participant_unread(db, existing.id, user.id), is_seller=False,
            product=product, counterpart=counterpart,
        )

    room = ChatRoom(type=data.type, title=product.title, product_id=product.id, verified=False)
    db.add(room)
    db.flush()  # room.id 확보

    db.add(ChatRoomParticipant(chat_room_id=room.id, user_id=user.id, unread_count=0))
    if product.created_by is not None:
        db.add(ChatRoomParticipant(chat_room_id=room.id, user_id=product.created_by, unread_count=0))
    db.commit()
    db.refresh(room)

    counterpart = _counterparts_by_room(db, [room.id], user.id).get(room.id)
    return _to_response(room, 0, is_seller=False, product=product, counterpart=counterpart)


def _find_existing_trade_room(db: Session, product_id: int, user_id: int) -> ChatRoom | None:
    return (
        db.query(ChatRoom)
        .join(ChatRoomParticipant, ChatRoomParticipant.chat_room_id == ChatRoom.id)
        .filter(
            ChatRoom.type == "TRADE",
            ChatRoom.product_id == product_id,
            ChatRoomParticipant.user_id == user_id,
        )
        .first()
    )


def existing_participant_unread(db: Session, chat_room_id: int, user_id: int) -> int:
    participant = _get_participant(db, chat_room_id, user_id)
    return participant.unread_count if participant else 0


def _counterparts_by_room(
    db: Session, room_ids: list[int], user_id: int
) -> dict[int, tuple[str, str | None]]:
    """방마다 "나 아닌 다른 참여자"의 (닉네임, 활동동네)를 모아온다.

    TRADE 채팅방은 항상 참여자가 정확히 2명(판매자/구매자)이라 방 하나당
    상대방도 하나로 고정된다 — N+1 방지를 위해 room_ids를 한 번에 조회.
    """
    if not room_ids:
        return {}
    rows = (
        db.query(ChatRoomParticipant.chat_room_id, User.nickname, Region.dong_name)
        .join(User, User.id == ChatRoomParticipant.user_id)
        .outerjoin(Region, Region.id == User.region_id)
        .filter(ChatRoomParticipant.chat_room_id.in_(room_ids), ChatRoomParticipant.user_id != user_id)
        .all()
    )
    return {room_id: (nickname, dong_name) for room_id, nickname, dong_name in rows}


def _to_response(
    room: ChatRoom,
    unread_count: int,
    is_seller: bool,
    product: Product | None = None,
    counterpart: tuple[str, str | None] | None = None,
) -> schema.ChatRoomResponse:
    nickname, dong_name = counterpart or (None, None)
    return schema.ChatRoomResponse(
        id=room.id,
        type=room.type,
        product_id=room.product_id,
        title=room.title,
        last_message=room.last_message,
        last_message_at=room.last_message_at,
        unread_count=unread_count,
        verified=room.verified,
        is_seller=is_seller,
        counterpart_nickname=nickname,
        counterpart_neighborhood_name=dong_name,
        product_thumbnail_url=storage.public_url(product.image_object_key)
        if product and product.image_object_key
        else None,
        product_price=product.desired_price if product else None,
        product_trade_status=product.trade_status if product else None,
    )


def list_my_chat_rooms(
    db: Session, user: User, page: int, size: int, product_id: int | None = None
) -> schema.ChatRoomListResponse:
    """내 채팅방 목록. product_id를 주면 그 상품에 걸린 채팅방만 걸러준다 —

    판매자가 자기 글의 "채팅하기"를 눌렀을 때 그 글에 관심 보인 구매자별
    채팅방을 N:1로 보여주는 용도(GET /api/v1/chats?product_id=...).
    """
    query = (
        db.query(ChatRoom, ChatRoomParticipant.unread_count, Product)
        .join(ChatRoomParticipant, ChatRoomParticipant.chat_room_id == ChatRoom.id)
        .outerjoin(Product, Product.id == ChatRoom.product_id)
        .filter(ChatRoomParticipant.user_id == user.id)
    )
    if product_id is not None:
        query = query.filter(ChatRoom.product_id == product_id)
    total = query.count()
    rows = (
        query.order_by(ChatRoom.last_message_at.desc(), ChatRoom.created_at.desc())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )
    counterparts = _counterparts_by_room(db, [room.id for room, _, _ in rows], user.id)
    items = [
        _to_response(
            room,
            unread_count,
            is_seller=(product is not None and product.created_by == user.id),
            product=product,
            counterpart=counterparts.get(room.id),
        )
        for room, unread_count, product in rows
    ]
    return schema.ChatRoomListResponse(items=items, total=total)


def _to_message_response(message: ChatMessage) -> schema.MessageResponse:
    return schema.MessageResponse(
        id=message.id,
        chat_room_id=message.chat_room_id,
        sender_id=message.sender_id,
        message_type=message.message_type,
        content=message.content,
        image_url=storage.public_url(message.image_object_key) if message.image_object_key else None,
        created_at=message.created_at,
    )


def _post_message(
    db: Session,
    room: ChatRoom,
    sender_id: int,
    message_type: str = "TEXT",
    content: str | None = None,
    image_object_key: str | None = None,
) -> ChatMessage:
    message = ChatMessage(
        chat_room_id=room.id,
        sender_id=sender_id,
        message_type=message_type,
        content=content,
        image_object_key=image_object_key,
    )
    db.add(message)
    db.flush()  # message.created_at 확보

    room.last_message = content if message_type == "TEXT" else "사진을 보냈습니다"
    room.last_message_at = message.created_at

    # 실시간 push는 범위 밖(REST 폴링 전제) — 발신자를 제외한 참여자의 안읽음만 증가.
    db.query(ChatRoomParticipant).filter(
        ChatRoomParticipant.chat_room_id == room.id,
        ChatRoomParticipant.user_id != sender_id,
    ).update({ChatRoomParticipant.unread_count: ChatRoomParticipant.unread_count + 1})
    return message


def presign_chat_image(
    db: Session, user: User, chat_room_id: int, data: schema.ImagePresignRequest
) -> schema.ImagePresignResponse:
    if db.get(ChatRoom, chat_room_id) is None:
        raise NotFoundError("채팅방을 찾을 수 없습니다.")
    if _get_participant(db, chat_room_id, user.id) is None:
        raise PermissionDeniedError("참여자만 이미지를 보낼 수 있습니다.")
    try:
        object_key = storage.build_object_key("chat", chat_room_id, data.content_type)
    except ValueError as e:
        raise AppError(str(e))
    return schema.ImagePresignResponse(
        upload_url=storage.presigned_put_url(object_key, data.content_type),
        object_key=object_key,
        image_url=storage.public_url(object_key),
    )


def send_message(
    db: Session, user: User, chat_room_id: int, data: schema.MessageCreateRequest
) -> schema.MessageResponse:
    room = db.get(ChatRoom, chat_room_id)
    if room is None:
        raise NotFoundError("채팅방을 찾을 수 없습니다.")
    if _get_participant(db, chat_room_id, user.id) is None:
        raise PermissionDeniedError("참여자만 메시지를 보낼 수 있습니다.")

    other_ids = [
        p.user_id
        for p in db.query(ChatRoomParticipant)
        .filter(ChatRoomParticipant.chat_room_id == chat_room_id, ChatRoomParticipant.user_id != user.id)
        .all()
    ]
    if any(safety_service.is_blocked(db, user.id, other_id) for other_id in other_ids):
        raise PermissionDeniedError("차단 관계에서는 메시지를 보낼 수 없습니다.")

    if data.message_type == "IMAGE":
        # presign이 내준 이 방의 키만 등록 가능 — 다른 방 폴더의 키를 갖다 붙이는 걸 막는다.
        prefix = f"chat/{chat_room_id}/"
        if not data.image_object_key.startswith(prefix):
            raise AppError("잘못된 이미지 키입니다.")

    message = _post_message(db, room, user.id, data.message_type, data.content, data.image_object_key)
    db.commit()
    db.refresh(message)
    return _to_message_response(message)


def leave_chat_room(db: Session, user: User, chat_room_id: int) -> None:
    participant = _get_participant(db, chat_room_id, user.id)
    if participant is None:
        if db.get(ChatRoom, chat_room_id) is None:
            raise NotFoundError("채팅방을 찾을 수 없습니다.")
        raise PermissionDeniedError("참여자만 나갈 수 있습니다.")
    db.delete(participant)
    db.commit()


def update_trade_status(
    db: Session, user: User, chat_room_id: int, data: schema.ChatRoomStatusUpdateRequest
) -> schema.MessageResponse:
    room = db.get(ChatRoom, chat_room_id)
    if room is None:
        raise NotFoundError("채팅방을 찾을 수 없습니다.")
    if room.product_id is None:
        raise AppError("상품이 삭제되어 상태를 변경할 수 없습니다.")

    # 소유자 확인은 update_product_status가 처리 (아니면 PermissionDeniedError) — 여기서 중복 확인하지 않는다.
    trade_service.update_product_status(db, user, room.product_id, data.trade_status)

    message = _post_message(db, room, user.id, "TEXT", _STATUS_MESSAGES[data.trade_status])
    db.commit()
    db.refresh(message)
    return _to_message_response(message)


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

    items = [_to_message_response(m) for m in rows]
    return schema.MessageListResponse(items=items, total=total)
