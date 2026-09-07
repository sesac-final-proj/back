from datetime import datetime
from typing import Literal

from pydantic import BaseModel, model_validator

from app.api.v1.trades.schema import ImagePresignRequest, ImagePresignResponse  # 이미지 presign 스키마 재사용
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
    product_id: int | None
    title: str
    last_message: str | None
    last_message_at: datetime | None
    unread_count: int
    verified: bool
    is_seller: bool


ChatRoomListResponse = Page[ChatRoomResponse]


ChatTradeStatus = Literal["SALE", "RESERVED", "SOLD"]


class ChatRoomStatusUpdateRequest(BaseModel):
    trade_status: ChatTradeStatus


MessageType = Literal["TEXT", "IMAGE"]


class MessageCreateRequest(BaseModel):
    message_type: MessageType = "TEXT"
    content: str | None = None
    image_object_key: str | None = None

    @model_validator(mode="after")
    def check_payload(self):
        if self.message_type == "TEXT" and not self.content:
            raise ValueError("TEXT 메시지는 content가 필요합니다.")
        if self.message_type == "IMAGE" and not self.image_object_key:
            raise ValueError("IMAGE 메시지는 image_object_key가 필요합니다.")
        return self


class MessageResponse(BaseModel):
    id: int
    chat_room_id: int
    sender_id: int
    message_type: MessageType
    content: str | None
    image_url: str | None = None
    created_at: datetime


MessageListResponse = Page[MessageResponse]
