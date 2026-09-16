"""차단/신고(safety) 자가 점검.

python -m tests.test_safety 로 실행. 실 DB에 임시 유저/지역/상품을
만들었다가 끝나면 전부 지운다.
"""

from app.api.v1.chats import service as chat_service
from app.api.v1.chats.schema import ChatRoomCreateRequest, MessageCreateRequest
from app.api.v1.safety import service as safety_service
from app.api.v1.safety.schema import ReportCreateRequest
from app.api.v1.trades import service as trade_service
from app.api.v1.trades.schema import ProductCreateRequest
from app.core.db import SessionLocal
from app.core.exceptions import AppError, NotFoundError, PermissionDeniedError
from app.core.security import hash_password
from app.models.block import UserBlock
from app.models.chat import ChatMessage, ChatRoom, ChatRoomParticipant
from app.models.product import Product
from app.models.region import Region
from app.models.report import Report
from app.models.user import User, UserRole


def main():
    db = SessionLocal()
    region = Region(dong_code="__SAFETY_SELFCHECK__", dong_name="자가검증동", gu_name="자가검증구", lat=0.0, lng=0.0)
    seller = User(
        email="__safety_selfcheck_seller__@example.com",
        password_hash=hash_password("x"), nickname="seller", role=UserRole.USER,
    )
    buyer = User(
        email="__safety_selfcheck_buyer__@example.com",
        password_hash=hash_password("x"), nickname="buyer", role=UserRole.USER,
    )
    db.add_all([region, seller, buyer])
    db.commit()
    db.refresh(region)
    db.refresh(seller)
    db.refresh(buyer)
    seller.region_id = region.id
    db.commit()

    product_id = None
    room_id = None
    report_id = None
    try:
        try:
            safety_service.block_user(db, buyer, buyer.id)
            raise AssertionError("본인 차단은 AppError여야 한다")
        except AppError:
            pass

        try:
            safety_service.block_user(db, buyer, -1)
            raise AssertionError("없는 사용자 차단은 404여야 한다")
        except NotFoundError:
            pass

        block_res = safety_service.block_user(db, buyer, seller.id)
        assert block_res.blocked is True
        block_again = safety_service.block_user(db, buyer, seller.id)  # 중복 차단 -> 그대로
        assert block_again.blocked is True
        assert db.query(UserBlock).filter_by(blocker_id=buyer.id, blocked_id=seller.id).count() == 1

        my_blocks = safety_service.list_my_blocks(db, buyer, page=1, size=20)
        assert my_blocks.total == 1 and my_blocks.items[0].blocked_id == seller.id

        assert safety_service.is_blocked(db, buyer.id, seller.id) is True
        assert safety_service.is_blocked(db, seller.id, buyer.id) is True  # 방향 무관

        # 차단된 상태에서 채팅 시작 시도 -> 403
        product = trade_service.create_product(
            db, seller, ProductCreateRequest(title="차단테스트 상품", category="기타")
        )
        product_id = product.id

        try:
            chat_service.create_chat_room(db, buyer, ChatRoomCreateRequest(type="TRADE", product_id=product.id))
            raise AssertionError("차단 관계에서 채팅 시작은 403이어야 한다")
        except PermissionDeniedError:
            pass

        # 차단 해제 후엔 정상 진행
        unblock_res = safety_service.unblock_user(db, buyer, seller.id)
        assert unblock_res.blocked is False
        assert safety_service.is_blocked(db, buyer.id, seller.id) is False
        assert safety_service.list_my_blocks(db, buyer, page=1, size=20).total == 0

        room = chat_service.create_chat_room(db, buyer, ChatRoomCreateRequest(type="TRADE", product_id=product.id))
        room_id = room.id

        # 대화 도중 판매자가 구매자를 차단하면 이후 메시지 전송이 막힌다
        safety_service.block_user(db, seller, buyer.id)
        try:
            chat_service.send_message(db, buyer, room.id, MessageCreateRequest(content="차단됐는데 보내짐?"))
            raise AssertionError("차단된 상대에게 메시지 전송은 403이어야 한다")
        except PermissionDeniedError:
            pass
        safety_service.unblock_user(db, seller, buyer.id)

        ok_msg = chat_service.send_message(db, buyer, room.id, MessageCreateRequest(content="차단 해제 후 정상 전송"))
        assert ok_msg.content == "차단 해제 후 정상 전송"

        # 신고
        report = safety_service.create_report(
            db, buyer, ReportCreateRequest(target_type="USER", target_id=seller.id, reason="스팸", description="테스트")
        )
        report_id = report.id
        assert report.status == "pending"
        assert report.reporter_id == buyer.id

        print("safety self-check OK")
    finally:
        if report_id is not None:
            db.query(Report).filter_by(id=report_id).delete()
        db.query(UserBlock).filter(
            (UserBlock.blocker_id.in_([buyer.id, seller.id])) | (UserBlock.blocked_id.in_([buyer.id, seller.id]))
        ).delete(synchronize_session=False)
        if room_id is not None:
            db.query(ChatMessage).filter_by(chat_room_id=room_id).delete()
            db.query(ChatRoomParticipant).filter_by(chat_room_id=room_id).delete()
            db.query(ChatRoom).filter_by(id=room_id).delete()
        if product_id is not None:
            db.query(Product).filter_by(id=product_id).delete()
        db.delete(seller)
        db.delete(buyer)
        db.delete(region)
        db.commit()
        db.close()


if __name__ == "__main__":
    main()
