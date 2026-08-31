from datetime import datetime
from typing import Literal

from pydantic import BaseModel, model_validator

from app.core.pagination import Page

ChatType = Literal["TRADE", "COMMUNITY", "GROUP", "SYSTEM"]


class ChatRoomCreateRequest(BaseModel):
    type: ChatType
    product_id: int | None = None

    @model_validator(mode="after")
    def check_trade_needs_product(self):
        if self.type == "TRADE" and self.product_id is None:
            raise ValueError("TRADE 타입 채팅방은 product_id가 필요합니다.")
        return self


class ChatRoomResponse(BaseModel):
    """carrot/mock_contract.py의 ChatRoom과 필드명을 맞춘다 (id는 int)."""

    model_config = {"from_attributes": True}

    id: int
    type: ChatType
    title: str
    last_message: str | None
    last_message_at: datetime | None
    unread_count: int
    verified: bool


ChatRoomListResponse = Page[ChatRoomResponse]


class MessageCreateRequest(BaseModel):
    content: str


class MessageResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    chat_room_id: int
    sender_id: int
    content: str
    created_at: datetime


MessageListResponse = Page[MessageResponse]
