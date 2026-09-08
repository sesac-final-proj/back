"""당근페이 송금 플로우(app/api/v1/wallet) 자가 점검.

python -m tests.test_wallet 로 실행. 실 DB에 임시 유저/지역/상품/채팅방을
만들었다가 끝나면 전부 지운다.
"""
from app.api.v1.chats import service as chat_service
from app.api.v1.chats.schema import ChatRoomCreateRequest
from app.api.v1.trades import service as trade_service
from app.api.v1.trades.schema import ProductCreateRequest
from app.api.v1.wallet import service as wallet_service
from app.api.v1.wallet.schema import PaymentCreateRequest
from app.core.db import SessionLocal
from app.core.exceptions import AppError, NotFoundError, PermissionDeniedError
from app.core.security import hash_password
from app.models.chat import ChatMessage, ChatRoom, ChatRoomParticipant
from app.models.favorite import ProductFavorite
from app.models.product import Product
from app.models.region import Region
from app.models.user import User, UserRole
from app.models.wallet import WalletTransaction


def main():
    db = SessionLocal()
    region = Region(dong_code="__WALLET_SELFCHECK__", dong_name="지갑검증동", gu_name="검증구", lat=0.0, lng=0.0)
    seller = User(
        email="__wallet_selfcheck_seller__@example.com",
        password_hash=hash_password("x"),
        nickname="wallet_seller",
        role=UserRole.USER,
    )
    buyer = User(
        email="__wallet_selfcheck_buyer__@example.com",
        password_hash=hash_password("x"),
        nickname="wallet_buyer",
        role=UserRole.USER,
    )
    stranger = User(
        email="__wallet_selfcheck_stranger__@example.com",
        password_hash=hash_password("x"),
        nickname="wallet_stranger",
        role=UserRole.USER,
    )
    db.add_all([region, seller, buyer, stranger])
    db.commit()
    db.refresh(region)
    db.refresh(seller)
    db.refresh(buyer)
    db.refresh(stranger)
    seller.region_id = region.id
    db.commit()

    product_id = None
    room_id = None
    try:
        assert seller.wallet_balance == 100000 and buyer.wallet_balance == 100000  # 가입 시 초기 지급

        product = trade_service.create_product(
            db, seller, ProductCreateRequest(title="지갑테스트상품", category="기타", desired_price=30000)
        )
        product_id = product.id

        room = chat_service.create_chat_room(db, buyer, ChatRoomCreateRequest(type="TRADE", product_id=product.id))
        room_id = room.id

        # 참여자 아닌 사람은 송금 불가
        try:
            wallet_service.send_payment(db, stranger, room.id, PaymentCreateRequest(amount=1000))
            raise AssertionError("참여자 아닌데 송금되면 안 된다")
        except PermissionDeniedError:
            pass

        # 판매자 본인은 자기 상품에 송금 불가
        try:
            wallet_service.send_payment(db, seller, room.id, PaymentCreateRequest(amount=1000))
            raise AssertionError("본인에게 송금하면 안 된다")
        except AppError:
            pass

        # 잔액 부족
        try:
            wallet_service.send_payment(db, buyer, room.id, PaymentCreateRequest(amount=999999))
            raise AssertionError("잔액 부족인데 송금되면 안 된다")
        except AppError:
            pass
        db.refresh(buyer)
        assert buyer.wallet_balance == 100000  # 실패한 시도는 잔액 안 건드림

        # 정상 송금
        message = wallet_service.send_payment(db, buyer, room.id, PaymentCreateRequest(amount=30000))
        assert message.message_type == "PAYMENT"
        assert message.payment_amount == 30000
        assert message.payment_id is not None

        db.refresh(buyer)
        db.refresh(seller)
        assert buyer.wallet_balance == 70000
        assert seller.wallet_balance == 130000

        wallet_tx = db.get(WalletTransaction, message.payment_id)
        assert wallet_tx.balance_after == 70000
        assert wallet_tx.sender_id == buyer.id and wallet_tx.receiver_id == seller.id

        # 상품 거래상태 자동 SOLD 전환 (문서 결정사항)
        assert trade_service.get_product_detail(db, product.id).trade_status == "SOLD"

        # 채팅방 last_message에도 반영
        assert db.get(ChatRoom, room.id).last_message == "당근페이로 송금을 보냈어요"

        # 이미 SOLD인 상품엔 재송금 불가
        try:
            wallet_service.send_payment(db, buyer, room.id, PaymentCreateRequest(amount=1000))
            raise AssertionError("이미 거래완료된 상품에 재송금되면 안 된다")
        except AppError:
            pass

        # 상세내역: 당사자만 조회 가능, 관점에 따라 is_sender가 뒤집힌다
        buyer_view = wallet_service.get_payment_detail(db, buyer, wallet_tx.id)
        assert buyer_view.is_sender is True and buyer_view.counterpart_nickname == "wallet_seller"
        assert buyer_view.amount == 30000 and buyer_view.balance_after == 70000

        seller_view = wallet_service.get_payment_detail(db, seller, wallet_tx.id)
        assert seller_view.is_sender is False and seller_view.counterpart_nickname == "wallet_buyer"

        try:
            wallet_service.get_payment_detail(db, stranger, wallet_tx.id)
            raise AssertionError("당사자 아닌데 상세내역 조회되면 안 된다")
        except PermissionDeniedError:
            pass

        # 목록 API(list_messages)에도 payment 필드가 채워져 나오는지
        page = chat_service.list_messages(db, buyer, room.id, page=1, size=20)
        payment_items = [m for m in page.items if m.message_type == "PAYMENT"]
        assert len(payment_items) == 1 and payment_items[0].payment_amount == 30000

        # 일반 메시지 API로는 PAYMENT 타입을 위조할 수 없다 (스키마 레벨에서 거부)
        from app.api.v1.chats.schema import MessageCreateRequest

        try:
            MessageCreateRequest(message_type="PAYMENT", content="위조 시도")
            raise AssertionError("MessageCreateRequest가 PAYMENT를 허용하면 안 된다")
        except ValueError:
            pass

        print("wallet self-check OK")
    finally:
        if room_id is not None:
            db.query(ChatMessage).filter_by(chat_room_id=room_id).delete()
            db.query(WalletTransaction).filter_by(chat_room_id=room_id).delete()
            db.query(ChatRoomParticipant).filter_by(chat_room_id=room_id).delete()
            db.query(ChatRoom).filter_by(id=room_id).delete()
        if product_id is not None:
            db.query(ProductFavorite).filter_by(product_id=product_id).delete()
            db.query(Product).filter_by(id=product_id).delete()
        db.delete(seller)
        db.delete(buyer)
        db.delete(stranger)
        db.delete(region)
        db.commit()
        db.close()


if __name__ == "__main__":
    main()
