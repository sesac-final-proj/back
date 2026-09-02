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
