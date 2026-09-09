from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class PointTransaction(Base):
    """꿈방울(포인트) 적립 1건 — 당근페이 결제 시 자동 적립, 아직 차감(기부) 로직은 없음.

    related_id는 적립 근거가 된 WalletTransaction — 일반결제(QR)는 mock이라
    wallet_transactions에 기록을 안 남기므로(app.api.v1.wallet.service.pay_by_qr)
    이 경우 항상 NULL이다.
    """

    __tablename__ = "point_transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    # DB 컬럼은 plain varchar — 값 검증은 schema.py의 Literal에서.
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    related_id: Mapped[int | None] = mapped_column(ForeignKey("wallet_transactions.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
