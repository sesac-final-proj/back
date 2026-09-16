from datetime import datetime
from typing import Literal

from pydantic import BaseModel

NoticeService = Literal["dream", "carrot"]


class NoticeItem(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    service: NoticeService
    title: str
    content: str
    created_at: datetime
    starts_at: datetime | None = None
    ends_at: datetime | None = None


class NoticeListResponse(BaseModel):
    items: list[NoticeItem]
    total: int
