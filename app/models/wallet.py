from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Store(Base):
    """QR 현장결제 대상 가맹점 — 실제 가맹점 연동 없이 이름만 등록해두는 mock.

    어드민이 등록하면(POST /wallet/stores) 그 id로 "<프론트도메인>/carrot?pay=<id>"
    URL을 QR로 인쇄해 매장에 비치한다. 손님 앱은 그 QR을 스캔(또는 URL 진입)해서
    id로 이름을 조회(GET /wallet/stores/{id})하고 금액을 입력해 결제한다.
    """

    __tablename__ = "stores"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    # 결제 화면 상단에 보여줄 매장 사진 — 선택사항(mock 매장은 없어도 됨).
    image_object_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


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
