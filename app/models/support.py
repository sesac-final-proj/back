import enum
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class SupportInquiryStatus(str, enum.Enum):
    WAITING = "WAITING"
    ANSWERED = "ANSWERED"
    CLOSED = "CLOSED"


class SupportInquiry(Base):
    __tablename__ = "support_inquiries"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[SupportInquiryStatus] = mapped_column(String(20), default=SupportInquiryStatus.WAITING, nullable=False)
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    answered_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User", foreign_keys=[user_id])
    messages = relationship("SupportInquiryMessage", back_populates="inquiry", cascade="all, delete-orphan", order_by="SupportInquiryMessage.created_at")


class SupportInquiryMessage(Base):
    __tablename__ = "support_inquiry_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    inquiry_id: Mapped[int] = mapped_column(ForeignKey("support_inquiries.id", ondelete="CASCADE"), nullable=False, index=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    author_role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    inquiry = relationship("SupportInquiry", back_populates="messages")
