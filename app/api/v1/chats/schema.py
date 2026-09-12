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


ChatTradeStatus = Literal["SALE", "RESERVED", "SOLD"]


class ChatRoomResponse(BaseModel):
    """carrot/mock_contract.py의 ChatRoom과 필드명을 맞춘다 (id는 int).

    counterpart_*/product_* 필드는 채팅방 목록/헤더 UI(상대방 닉네임·동네,
    물품 사진·거래상태·가격)를 이 응답 하나로 그릴 수 있게 얹었다 — 프론트가
    상세 API를 따로 또 부르지 않아도 되게.
    """

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
    counterpart_nickname: str | None = None
    # 실제 가입 유저의 매너온도 시스템은 아직 없음(Product.seller_manner_temp는 크롤링
    # 원본 스냅샷이라 채팅 상대와 무관) — 항상 None, 도입되면 여기서 채워주면 됨.
    counterpart_manner_temp: float | None = None
    counterpart_neighborhood_name: str | None = None
    product_thumbnail_url: str | None = None
    product_price: int | None = None
    product_trade_status: ChatTradeStatus | None = None


ChatRoomListResponse = Page[ChatRoomResponse]


class ChatRoomStatusUpdateRequest(BaseModel):
    trade_status: ChatTradeStatus


MessageType = Literal["TEXT", "IMAGE", "PAYMENT"]
# PAYMENT는 app.api.v1.wallet의 송금 API를 통해서만 생성된다 — 돈이 오가는 메시지를
# 일반 메시지 API로 위조 못 하게, 생성 요청 스키마에는 아예 이 값을 허용하지 않는다.
CreatableMessageType = Literal["TEXT", "IMAGE"]


class MessageCreateRequest(BaseModel):
    message_type: CreatableMessageType = "TEXT"
    content: str | None = None
    image_object_key: str | None = None

    @model_validator(mode="after")
    def check_payload(self):
        if self.message_type == "TEXT" and not self.content:
            raise ValueError("TEXT 메시지는 content가 필요합니다.")
        if self.message_type == "IMAGE" and not self.image_object_key:
            raise ValueError("IMAGE 메시지는 image_object_key가 필요합니다.")
        return self


class MessagePaymentInfo(BaseModel):
    transaction_id: int
    amount: int
    # 송금한 사람(sender) 기준 거래 후 잔액.
    balance_after: int


class MessageResponse(BaseModel):
    id: int
    chat_room_id: int
    sender_id: int
    message_type: MessageType
    content: str | None
    image_url: str | None = None
    # message_type == "PAYMENT"일 때만 채워짐 — 프론트가 이 값 하나로 송금 카드
    # 버블/상세화면을 그린다(별도 상세 API 호출 없음).
    payment: MessagePaymentInfo | None = None
    created_at: datetime


class MessageListResponse(BaseModel):
    items: list[MessageResponse]
    total: int
    # 상대방이 메시지함을 마지막으로 연 시각 — 프론트가 "내가 보낸 메시지 중 이 시각
    # 이후 것"만 안읽음(1)으로 표시한다. 상대가 한 번도 연 적 없으면 None(전부 안읽음).
    counterpart_last_read_at: datetime | None = None
