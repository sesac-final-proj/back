from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class WalletTransaction(Base):
    """당근페이 송금 1건 (mock — 실제 계좌 연동 없음, User.wallet_balance끼리 이체).

    product_id는 상품이 나중에 삭제돼도 송금 기록은 남아야 해서 nullable —
    trades/service.py의 delete_product가 ChatRoom.product_id와 동일하게 참조만 끊는다.
    """

    __tablename__ = "wallet_transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    chat_room_id: Mapped[int] = mapped_column(ForeignKey("chat_rooms.id"), nullable=False)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"), nullable=True)
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    receiver_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    # sender 기준 송금 후 잔액 — 상세내역 화면의 "거래후잔액".
    balance_after: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
