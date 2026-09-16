from datetime import datetime

from pydantic import BaseModel, Field

from app.core.pagination import Page


class CommunityPostCreateRequest(BaseModel):
    category: str = Field(default="일반", max_length=30)
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1)
    thumbnail_url: str | None = Field(default=None, max_length=500)


class CommunityPostUpdateRequest(BaseModel):
    category: str | None = Field(default=None, max_length=30)
    title: str | None = Field(default=None, min_length=1, max_length=200)
    content: str | None = Field(default=None, min_length=1)
    thumbnail_url: str | None = Field(default=None, max_length=500)


class CommunityPostCreated(BaseModel):
    id: int


class CommunityPostListItem(BaseModel):
    id: int
    category: str
    title: str
    content: str
    neighborhood_name: str
    author_id: int
    author_nickname: str
    created_at: datetime
    view_count: int
    comment_count: int
    reaction_count: int
    thumbnail_url: str | None = None
    is_mine: bool = False
    is_reacted: bool = False


CommunityPostListResponse = Page[CommunityPostListItem]


class CommunityPostEmotionToggleResponse(BaseModel):
    reacted: bool
    reaction_count: int


class CommunityPostCommentCreateRequest(BaseModel):
    content: str = Field(min_length=1)


class CommunityPostCommentItem(BaseModel):
    id: int
    post_id: int
    author_id: int
    author_nickname: str
    content: str
    created_at: datetime
    is_mine: bool = False


class CommunityPostCommentListResponse(BaseModel):
    items: list[CommunityPostCommentItem]
    total: int


class CommunityPostCommentCreated(BaseModel):
    comment: CommunityPostCommentItem
    comment_count: int
