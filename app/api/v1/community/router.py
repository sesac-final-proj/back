from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.v1.community import schema, service
from app.core.db import get_db
from app.core.deps import get_current_user, get_current_user_optional
from app.models.user import User

router = APIRouter(prefix="/api/v1/community", tags=["커뮤니티"])


@router.get("/posts", response_model=schema.CommunityPostListResponse)
def list_posts(
    region_id: int | None = None,
    category: str | None = None,
    q: str | None = None,
    page: int = 1,
    size: int = 60,
    user: User | None = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    return service.list_posts(db, user, region_id, category, q, page, size)


@router.post("/posts", response_model=schema.CommunityPostCreated, status_code=status.HTTP_201_CREATED)
def create_post(
    body: schema.CommunityPostCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    post = service.create_post(db, user, body)
    return schema.CommunityPostCreated(id=post.id)


@router.get("/posts/{post_id}", response_model=schema.CommunityPostListItem)
def get_post(
    post_id: int,
    user: User | None = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    return service.get_post_detail(db, user, post_id)


@router.patch("/posts/{post_id}", response_model=schema.CommunityPostListItem)
def update_post(
    post_id: int,
    body: schema.CommunityPostUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service.update_post(db, user, post_id, body)
    return service.get_post_detail(db, user, post_id)


@router.patch("/posts/{post_id}/delete", status_code=status.HTTP_204_NO_CONTENT)
def delete_post(
    post_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service.soft_delete_post(db, user, post_id)


@router.post("/posts/{post_id}/emotion", response_model=schema.CommunityPostEmotionToggleResponse)
def toggle_emotion(
    post_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return service.toggle_emotion(db, user, post_id)


@router.get("/posts/{post_id}/comments", response_model=schema.CommunityPostCommentListResponse)
def list_comments(
    post_id: int,
    user: User | None = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    return service.list_comments(db, user, post_id)


@router.post(
    "/posts/{post_id}/comments",
    response_model=schema.CommunityPostCommentCreated,
    status_code=status.HTTP_201_CREATED,
)
def create_comment(
    post_id: int,
    body: schema.CommunityPostCommentCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return service.create_comment(db, user, post_id, body)


@router.delete("/posts/{post_id}/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_comment(
    post_id: int,
    comment_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service.delete_comment(db, user, post_id, comment_id)
