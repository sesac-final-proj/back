"""ChatRoomParticipant.last_read_at / counterpart_last_read_at 자가 점검.

python -m tests.test_chat_read_receipt 로 실행. 실 DB에 임시 유저/지역/상품/
채팅방을 만들었다가 끝나면 전부 지운다 (스키마 변경 없음, 일반 CRUD만 수행).
"""

from app.api.v1.chats import service as chat_service
from app.api.v1.chats.schema import ChatRoomCreateRequest, MessageCreateRequest
from app.api.v1.trades import service as trade_service
from app.api.v1.trades.schema import ProductCreateRequest
from app.core.db import SessionLocal
from app.core.security import hash_password
from app.models.chat import ChatMessage, ChatRoom, ChatRoomParticipant
from app.models.product import Product
from app.models.region import Region
from app.models.user import User, UserRole


def main():
    db = SessionLocal()
    region = Region(
        dong_code="__RR_SELFCHECK__",
        dong_name="읽음표시자가검증동",
        gu_name="읽음표시자가검증구",
        lat=0.0,
        lng=0.0,
    )
    owner = User(
        email="__read_receipt_selfcheck_owner__@example.com",
        password_hash=hash_password("x"),
        nickname="rr_owner",
        role=UserRole.USER,
    )
    other = User(
        email="__read_receipt_selfcheck_other__@example.com",
        password_hash=hash_password("x"),
        nickname="rr_other",
        role=UserRole.USER,
    )
    db.add_all([region, owner, other])
    db.commit()
    db.refresh(region)
    db.refresh(owner)
    db.refresh(other)
    owner.region_id = region.id
    db.commit()
    db.refresh(owner)

    product_id = None
    room_id = None
    try:
        product = trade_service.create_product(
            db, owner, ProductCreateRequest(title="읽음표시 테스트 상품", category="기타", desired_price=1000)
        )
        product_id = product.id

        room = chat_service.create_chat_room(db, other, ChatRoomCreateRequest(type="TRADE", product_id=product.id))
        room_id = room.id

        # 둘 다 아직 메시지함을 연 적 없음 -> last_read_at 전부 None
        never_read = chat_service.list_messages(db, other, room.id, page=1, size=20)
        assert never_read.counterpart_last_read_at is None, "owner가 아직 안 열었으면 None이어야 한다"

        # other가 메시지를 보낸다 -> owner가 안 읽은 상태
        chat_service.send_message(db, other, room.id, MessageCreateRequest(content="이거 아직 파나요?"))

        # owner가 아직 메시지함을 안 열었으니, other가 다시 조회해도 여전히 None
        still_unread = chat_service.list_messages(db, other, room.id, page=1, size=20)
        assert still_unread.counterpart_last_read_at is None, "owner가 안 읽었는데 값이 생기면 안 된다"

        # owner가 메시지함을 연다 -> owner.last_read_at이 채워짐. other는 이미 위에서
        # 두 번 열었으므로(never_read/still_unread), owner 입장에서 보는 상대(other)의
        # last_read_at은 이미 값이 있어야 한다.
        owner_view = chat_service.list_messages(db, owner, room.id, page=1, size=20)
        assert owner_view.counterpart_last_read_at is not None, "other는 이미 메시지함을 연 적 있다"

        owner_participant = (
            db.query(ChatRoomParticipant)
            .filter(ChatRoomParticipant.chat_room_id == room.id, ChatRoomParticipant.user_id == owner.id)
            .first()
        )
        assert owner_participant.last_read_at is not None, "list_messages 호출 시 last_read_at이 채워져야 한다"

        # other가 다시 조회하면, 이제 owner.last_read_at이 counterpart_last_read_at로 보여야 한다
        now_read = chat_service.list_messages(db, other, room.id, page=1, size=20)
        assert now_read.counterpart_last_read_at is not None, "owner가 읽었으면 시각이 채워져야 한다"
        assert now_read.counterpart_last_read_at == owner_participant.last_read_at

        print("OK: chat read-receipt self-check passed")
    finally:
        if room_id is not None:
            db.query(ChatMessage).filter_by(chat_room_id=room_id).delete()
            db.query(ChatRoomParticipant).filter_by(chat_room_id=room_id).delete()
            db.query(ChatRoom).filter_by(id=room_id).delete()
        if product_id is not None:
            db.query(Product).filter_by(id=product_id).delete()
        db.query(User).filter(User.id.in_([owner.id, other.id])).delete(synchronize_session=False)
        db.query(Region).filter_by(id=region.id).delete()
        db.commit()
        db.close()


if __name__ == "__main__":
    main()
