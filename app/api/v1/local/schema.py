from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.core.pagination import Page

NoticeSource = Literal["공사", "단수", "날씨"]


class NoticeSummary(BaseModel):
    occurred_at: str | None
    location: str | None
    impact: str | None
    action_guide: str | None


class NoticeItem(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    source: NoticeSource
    region_name: str | None
    title: str
    summary: NoticeSummary | None
    collected_at: datetime


class NoticeMapItem(BaseModel):
    id: int
    title: str
    source: NoticeSource
    lat: float
    lng: float


class CollectResultItem(BaseModel):
    source: NoticeSource
    collected_count: int


class CollectTriggerResponse(BaseModel):
    results: list[CollectResultItem]


NoticeListResponse = Page[NoticeItem]


class DangerSignalItem(BaseModel):
    id: str
    name: str
    category: Literal["danger"] = "danger"
    neighborhood_name: str | None = None
    sigungu: str | None = None
    distance: str
    open_now: bool = True
    liked: bool = False
    summary: str
    lat: float
    lng: float
    risk_type: str | None = None
    observed_at: datetime | None = None
    source_url: str | None = None


class DangerSignalListResponse(BaseModel):
    items: list[DangerSignalItem]
    total: int


class RegionItem(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    dong_name: str
    gu_name: str


class RegionListResponse(BaseModel):
    items: list[RegionItem]


CongestionLevel = Literal["여유", "보통", "약간 붐빔", "붐빔", "정보없음"]


class PlaceRecommendation(BaseModel):
    """프론트 GajiMap.tsx의 클라이언트 로직과 필드명을 그대로 맞춘다."""

    name: str
    lat: float
    lng: float
    distanceMeters: int
    congestionLevel: CongestionLevel
    congestionMessage: str | None = None


class PlaceRecommendationResponse(BaseModel):
    results: list[PlaceRecommendation]
