from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.core.pagination import Page


class BlockResponse(BaseModel):
    blocked: bool


class BlockedUserItem(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    blocked_id: int
    created_at: datetime


BlockedUserListResponse = Page[BlockedUserItem]


ReportTargetType = Literal["USER", "PRODUCT", "MESSAGE"]


class ReportCreateRequest(BaseModel):
    target_type: ReportTargetType
    target_id: int
    reason: str
    description: str | None = None


class ReportCreated(BaseModel):
    id: int
