from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.core.pagination import Page


class RegionDataCount(BaseModel):
    """"오류"는 크롤링 시점에 Transaction.region_id가 안 채워진(동네 매칭 실패)
    건수다 — 그 외 검증 규칙은 아직 없다. 매칭 실패 건은 특정 동네로 묶을 수
    없어서 region_name="지역 매칭 실패" 한 행으로 합쳐 보여준다."""

    region_name: str
    normal_count: int
    error_count: int
    error_rate: float


class CategoryDataCount(BaseModel):
    category: str
    normal_count: int
    error_count: int
    error_rate: float


class CollectionErrorItem(BaseModel):
    source: str
    message: str
    occurred_at: datetime


class DataStatusResponse(BaseModel):
    region_counts: list[RegionDataCount]
    category_counts: list[CategoryDataCount]
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
