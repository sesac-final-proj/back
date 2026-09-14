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
    """당근페이 송금/결제/충전 1건 (mock — 실제 계좌 연동 없음, User.wallet_balance끼리 이체).

    세 종류를 한 테이블에 같이 담는다: (1) 채팅 기반 P2P 송금(TRANSFER, chat_room_id/
    receiver_id 있음), (2) QR 현장결제(QR_PAYMENT, store_id 있음), (3) 충전(CHARGE,
    상대가 없어 receiver_id/store_id 둘 다 없음 — sender_id만 "이 잔액이 바뀐 사람"으로 채움).
    DB 컬럼은 plain varchar(Postgres enum 아님) — 값 검증은 route/service 쪽에서.

    product_id는 상품이 나중에 삭제돼도 송금 기록은 남아야 해서 nullable —
    trades/service.py의 delete_product가 ChatRoom.product_id와 동일하게 참조만 끊는다.
    """

    __tablename__ = "wallet_transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[str] = mapped_column(String(20), nullable=False, server_default="TRANSFER")
    chat_room_id: Mapped[int | None] = mapped_column(ForeignKey("chat_rooms.id"), nullable=True)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"), nullable=True)
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    receiver_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    store_id: Mapped[int | None] = mapped_column(ForeignKey("stores.id"), nullable=True)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    # sender 기준 결제/충전 후 잔액 — 상세내역 화면의 "거래후잔액".
    balance_after: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
