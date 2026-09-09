from sqlalchemy.orm import Session

from app.api.v1.chats import service as chat_service
from app.api.v1.chats import schema as chat_schema
from app.api.v1.wallet import schema
from app.core import storage
from app.core.exceptions import AppError, NotFoundError, PermissionDeniedError
from app.models.chat import ChatRoom
from app.models.product import Product
from app.models.user import User
from app.models.wallet import WalletTransaction


def get_balance(user: User) -> schema.WalletBalanceResponse:
    return schema.WalletBalanceResponse(balance=user.wallet_balance)


# ponytail: 실제 계좌 자동충전 연동은 스코프 밖(docs/carrot-pay-trade-flow-plan.md 6절) —
# 은행 계좌 검증 없이 잔액만 그대로 올려준다. 송금과 달리 상대가 없어 wallet_transactions에
# 남길 것도 없으니 잔액만 갱신.
def charge_wallet(db: Session, user: User, amount: int) -> schema.WalletBalanceResponse:
    user.wallet_balance += amount
    db.commit()
    db.refresh(user)
    return schema.WalletBalanceResponse(balance=user.wallet_balance)


# ponytail: QR 결제도 charge_wallet과 같은 이유로 mock — 가맹점은 DB에 없는 이름 문자열일
# 뿐이라 wallet_transactions에 남길 상대(receiver)가 없다. 잔액 차감만 한다.
def pay_by_qr(db: Session, user: User, data: schema.QrPayRequest) -> schema.WalletBalanceResponse:
    if user.wallet_balance < data.amount:
        raise AppError("잔액이 부족합니다.")
    user.wallet_balance -= data.amount
    db.commit()
    db.refresh(user)
    return schema.WalletBalanceResponse(balance=user.wallet_balance)


def send_payment(
    db: Session, user: User, chat_room_id: int, data: schema.PaymentCreateRequest
) -> chat_schema.MessageResponse:
    """당근페이 송금. 구매자(user) -> 판매자(product.created_by)로만 보낼 수 있다.

    성공하면: 잔액 이체 -> wallet_transactions 기록 -> 채팅방에 PAYMENT 메시지 ->
    상품 거래상태를 SOLD로 자동전환(문서 결정사항 — 판매자 별도 확인 없음).
    """
    room = db.get(ChatRoom, chat_room_id)
    if room is None:
        raise NotFoundError("채팅방을 찾을 수 없습니다.")
    if chat_service._get_participant(db, chat_room_id, user.id) is None:
        raise PermissionDeniedError("참여자만 송금할 수 있습니다.")
    if room.product_id is None:
        raise AppError("상품이 삭제되어 송금할 수 없습니다.")

    product = db.get(Product, room.product_id)
    if product is None:
        raise NotFoundError("상품을 찾을 수 없습니다.")
    if product.created_by is None:
        raise AppError("판매자 정보가 없어 송금할 수 없습니다.")
    if product.created_by == user.id:
        raise AppError("본인에게 송금할 수 없습니다.")
    if product.trade_status == "SOLD":
        raise AppError("이미 거래완료된 상품입니다.")

    amount = data.amount
    if user.wallet_balance < amount:
        raise AppError("잔액이 부족합니다.")

    receiver = db.get(User, product.created_by)
    if receiver is None:
        raise NotFoundError("판매자를 찾을 수 없습니다.")

    user.wallet_balance -= amount
    receiver.wallet_balance += amount
    db.flush()  # balance_after에 반영할 sender 잔액 확정

    wallet_tx = WalletTransaction(
        chat_room_id=room.id,
        product_id=product.id,
        sender_id=user.id,
        receiver_id=receiver.id,
        amount=amount,
        balance_after=user.wallet_balance,
    )
    db.add(wallet_tx)
    db.flush()  # wallet_tx.id 확보 (메시지에 연결)

    message = chat_service._post_message(db, room, user.id, "PAYMENT", payment_id=wallet_tx.id)
    product.trade_status = "SOLD"
    db.commit()
    db.refresh(message)

    return chat_service._to_message_response(message, payment=(amount, wallet_tx.balance_after))


def get_payment_detail(db: Session, user: User, wallet_tx_id: int) -> schema.PaymentDetailResponse:
    wallet_tx = db.get(WalletTransaction, wallet_tx_id)
    if wallet_tx is None:
        raise NotFoundError("송금 내역을 찾을 수 없습니다.")
    if user.id not in (wallet_tx.sender_id, wallet_tx.receiver_id):
        raise PermissionDeniedError("본인 거래만 조회할 수 있습니다.")

    is_sender = user.id == wallet_tx.sender_id
    counterpart_id = wallet_tx.receiver_id if is_sender else wallet_tx.sender_id
    counterpart = db.get(User, counterpart_id)
    product = db.get(Product, wallet_tx.product_id) if wallet_tx.product_id else None

    return schema.PaymentDetailResponse(
        id=wallet_tx.id,
        chat_room_id=wallet_tx.chat_room_id,
        product_id=wallet_tx.product_id,
        product_title=product.title if product else None,
        product_thumbnail_url=storage.public_url(product.image_object_key)
        if product and product.image_object_key
        else None,
        counterpart_nickname=counterpart.nickname if counterpart else None,
        is_sender=is_sender,
        amount=wallet_tx.amount,
        balance_after=wallet_tx.balance_after,
        created_at=wallet_tx.created_at,
    )
