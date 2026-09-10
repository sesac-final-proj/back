from datetime import datetime

from pydantic import BaseModel, Field


class InquiryCreateRequest(BaseModel):
    title: str = Field(min_length=2, max_length=120)
    content: str = Field(min_length=5, max_length=4000)


class InquiryAnswerRequest(BaseModel):
    answer: str = Field(min_length=2, max_length=4000)


class InquiryMessageRequest(BaseModel):
    content: str = Field(min_length=2, max_length=4000)


class InquiryMessageResponse(BaseModel):
    id: int | None = None
    author_role: str
    content: str
    created_at: datetime


class InquiryResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    user_id: int
    title: str
    content: str
    status: str
    answer: str | None
    answered_at: datetime | None
    closed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    user_nickname: str | None = None
    user_email: str | None = None
    messages: list[InquiryMessageResponse] = Field(default_factory=list)


class InquiryListResponse(BaseModel):
    items: list[InquiryResponse]
    total: int
