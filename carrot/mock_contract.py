from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


TradeStatus = Literal["SALE", "RESERVED", "SOLD"]
TradeType = Literal["SALE", "FREE"]
ChatType = Literal["TRADE", "COMMUNITY", "GROUP", "SYSTEM"]


@dataclass(frozen=True)
class ProductListItem:
    id: str
    title: str
    neighborhood_name: str
    created_at: str
    price: int | None
    trade_status: TradeStatus
    trade_type: TradeType
    chat_count: int
    favorite_count: int


@dataclass(frozen=True)
class ChatRoom:
    id: str
    type: ChatType
    title: str
    last_message: str
    last_message_at: str
    unread_count: int
    verified: bool


MOCK_PRODUCTS: tuple[ProductListItem, ...] = (
    ProductListItem("p1", "삼성 갤럭시 탭 A7 SM-T505N", "위례", "17시간 전", 50000, "RESERVED", "SALE", 1, 9),
    ProductListItem("p2", "원목 사이드 테이블", "공릉", "방금 전", 28000, "SALE", "SALE", 0, 2),
    ProductListItem("p3", "버거킹 할인 쿠폰 무료나눔", "당산 2동", "2일 전", None, "SALE", "FREE", 5, 0),
)

MOCK_CHATS: tuple[ChatRoom, ...] = (
    ChatRoom("chat1", "SYSTEM", "가지스토어", "앱 첫 화면 쿠폰을 준비했어요.", "4일 전", 1, True),
    ChatRoom("chat2", "TRADE", "원목 사이드 테이블", "오늘 저녁 7시에 거래 가능하실까요?", "방금 전", 15, False),
)
