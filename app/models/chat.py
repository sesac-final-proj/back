from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class ChatRoom(Base):
    __tablename__ = "chat_rooms"

    id: Mapped[int] = mapped_column(primary_key=True)
    # DB 컬럼은 plain varchar (Postgres enum 아님) — 값 검증은 schema.py의 Literal에서.
    type: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(255))
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"), nullable=True)
    last_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ChatRoomParticipant(Base):
    __tablename__ = "chat_room_participants"

    id: Mapped[int] = mapped_column(primary_key=True)
    chat_room_id: Mapped[int] = mapped_column(ForeignKey("chat_rooms.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    unread_count: Mapped[int] = mapped_column(Integer, default=0)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    chat_room_id: Mapped[int] = mapped_column(ForeignKey("chat_rooms.id"))
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    message_type: Mapped[str] = mapped_column(String(10), default="TEXT", server_default="TEXT")
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    # NCP Object Storage 상의 key ("chat/{chat_room_id}/..."). 공개 URL은
    # app.core.storage.public_url()로 그때그때 조립한다 (Product.image_object_key와 동일 패턴).
    image_object_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # message_type == "PAYMENT"일 때만 채워짐 — 어떤 당근페이 송금 건인지 연결.
    payment_id: Mapped[int | None] = mapped_column(ForeignKey("wallet_transactions.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
