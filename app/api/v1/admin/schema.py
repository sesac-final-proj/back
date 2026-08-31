from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.core.pagination import Page


class RegionDataCount(BaseModel):
    region_name: str
    transaction_count: int


class CollectionErrorItem(BaseModel):
    model_config = {"from_attributes": True}

    source: str
    message: str
    occurred_at: datetime


class DataStatusResponse(BaseModel):
    region_counts: list[RegionDataCount]
    recent_errors: list[CollectionErrorItem]


NoticeStatus = Literal["draft", "published", "hidden"]


class NoticeListItem(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    source: str
    region_name: str | None
    title: str
    status: NoticeStatus
    collected_at: datetime


class NoticeStatusUpdateRequest(BaseModel):
    status: NoticeStatus


class AlertCreatedResponse(BaseModel):
    id: int
    notice_id: int
    created_at: datetime


NoticeListResponse = Page[NoticeListItem]
