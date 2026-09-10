from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.api.v1.community import schema
from app.core.exceptions import AppError, NotFoundError, PermissionDeniedError
from app.models.community import CommunityPost, CommunityPostComment, CommunityPostEmotion
from app.models.region import Region
from app.models.user import User


def create_post(db: Session, user: User, data: schema.CommunityPostCreateRequest) -> CommunityPost:
    if user.region_id is None:
        raise AppError("활동동네를 먼저 설정해주세요.")

    post = CommunityPost(
        user_id=user.id,
        region_id=user.region_id,
        category=data.category or "일반",
        title=data.title,
        content=data.content,
        thumbnail_url=data.thumbnail_url,
        view_count=0,
        emotion_count=0,
        comment_count=0,
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    return post


def _get_visible_post(db: Session, post_id: int) -> CommunityPost:
    post = db.get(CommunityPost, post_id)
    if post is None or post.deleted_at is not None:
        raise NotFoundError("게시글을 찾을 수 없습니다.")
    return post


def _to_list_item(
    db: Session,
    post: CommunityPost,
    dong_name: str,
    author_nickname: str,
    user: User | None,
) -> schema.CommunityPostListItem:
    is_reacted = False
    if user is not None:
        is_reacted = (
            db.query(CommunityPostEmotion)
            .filter(CommunityPostEmotion.post_id == post.id, CommunityPostEmotion.user_id == user.id)
            .first()
            is not None
        )
    return schema.CommunityPostListItem(
        id=post.id,
        category=post.category,
        title=post.title,
        content=post.content,
        neighborhood_name=dong_name,
        author_id=post.user_id,
        author_nickname=author_nickname,
        created_at=post.created_at,
        view_count=post.view_count,
        comment_count=post.comment_count,
        reaction_count=post.emotion_count,
        thumbnail_url=post.thumbnail_url,
        is_mine=user is not None and post.user_id == user.id,
        is_reacted=is_reacted,
    )


def list_posts(
    db: Session,
    user: User | None,
    region_id: int | None,
    category: str | None,
    q: str | None,
    page: int,
    size: int,
) -> schema.CommunityPostListResponse:
    query = (
        db.query(CommunityPost, Region.dong_name, User.nickname)
        .join(Region, CommunityPost.region_id == Region.id)
        .join(User, CommunityPost.user_id == User.id)
        .filter(CommunityPost.deleted_at.is_(None))
    )
    if region_id is not None:
        query = query.filter(CommunityPost.region_id == region_id)
    if category is not None:
        query = query.filter(CommunityPost.category == category)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(CommunityPost.title.ilike(like), CommunityPost.content.ilike(like)))

    total = query.count()
    rows = (
        query.order_by(CommunityPost.created_at.desc(), CommunityPost.id.desc())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )
    items = [_to_list_item(db, post, dong_name, nickname, user) for post, dong_name, nickname in rows]
    return schema.CommunityPostListResponse(items=items, total=total)


def get_post_detail(db: Session, user: User | None, post_id: int) -> schema.CommunityPostListItem:
    row = (
        db.query(CommunityPost, Region.dong_name, User.nickname)
        .join(Region, CommunityPost.region_id == Region.id)
        .join(User, CommunityPost.user_id == User.id)
        .filter(CommunityPost.id == post_id, CommunityPost.deleted_at.is_(None))
        .first()
    )
    if row is None:
        raise NotFoundError("게시글을 찾을 수 없습니다.")
    post, dong_name, nickname = row
    return _to_list_item(db, post, dong_name, nickname, user)


def update_post(
    db: Session,
    user: User,
    post_id: int,
    data: schema.CommunityPostUpdateRequest,
) -> CommunityPost:
    post = _get_visible_post(db, post_id)
    if post.user_id != user.id:
        raise PermissionDeniedError("본인 게시글만 수정할 수 있습니다.")

    for field, value in data.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(post, field, value)
    db.commit()
    db.refresh(post)
    return post


def soft_delete_post(db: Session, user: User, post_id: int) -> None:
    post = _get_visible_post(db, post_id)
    if post.user_id != user.id:
        raise PermissionDeniedError("본인 게시글만 삭제할 수 있습니다.")

    post.deleted_at = func.now()
    db.commit()


def toggle_emotion(db: Session, user: User, post_id: int) -> schema.CommunityPostEmotionToggleResponse:
    post = _get_visible_post(db, post_id)
    existing = (
        db.query(CommunityPostEmotion)
        .filter(CommunityPostEmotion.user_id == user.id, CommunityPostEmotion.post_id == post_id)
        .first()
    )
    if existing is None:
        db.add(CommunityPostEmotion(user_id=user.id, post_id=post_id))
        post.emotion_count = max((post.emotion_count or 0) + 1, 0)
        reacted = True
    else:
        db.delete(existing)
        post.emotion_count = max((post.emotion_count or 0) - 1, 0)
        reacted = False
    db.commit()
    db.refresh(post)
    return schema.CommunityPostEmotionToggleResponse(reacted=reacted, reaction_count=post.emotion_count)


def _to_comment_item(
    comment: CommunityPostComment,
    author_nickname: str,
    user: User | None,
) -> schema.CommunityPostCommentItem:
    return schema.CommunityPostCommentItem(
        id=comment.id,
        post_id=comment.post_id,
        author_id=comment.user_id,
        author_nickname=author_nickname,
        content=comment.content,
        created_at=comment.created_at,
        is_mine=user is not None and comment.user_id == user.id,
    )


def list_comments(db: Session, user: User | None, post_id: int) -> schema.CommunityPostCommentListResponse:
    _get_visible_post(db, post_id)
    rows = (
        db.query(CommunityPostComment, User.nickname)
        .join(User, CommunityPostComment.user_id == User.id)
        .filter(CommunityPostComment.post_id == post_id)
        .order_by(CommunityPostComment.created_at.asc(), CommunityPostComment.id.asc())
        .all()
    )
    return schema.CommunityPostCommentListResponse(
        items=[_to_comment_item(comment, nickname, user) for comment, nickname in rows],
        total=len(rows),
    )


def create_comment(
    db: Session,
    user: User,
    post_id: int,
    data: schema.CommunityPostCommentCreateRequest,
) -> schema.CommunityPostCommentCreated:
    post = _get_visible_post(db, post_id)
    comment = CommunityPostComment(post_id=post_id, user_id=user.id, content=data.content)
    db.add(comment)
    post.comment_count = max((post.comment_count or 0) + 1, 0)
    db.commit()
    db.refresh(comment)
    db.refresh(post)
    return schema.CommunityPostCommentCreated(
        comment=_to_comment_item(comment, user.nickname, user),
        comment_count=post.comment_count,
    )


def delete_comment(db: Session, user: User, post_id: int, comment_id: int) -> int:
    post = _get_visible_post(db, post_id)
    comment = (
        db.query(CommunityPostComment)
        .filter(CommunityPostComment.id == comment_id, CommunityPostComment.post_id == post_id)
        .first()
    )
    if comment is None:
        raise NotFoundError("댓글을 찾을 수 없습니다.")
    if comment.user_id != user.id:
        raise PermissionDeniedError("본인 댓글만 삭제할 수 있습니다.")

    db.delete(comment)
    post.comment_count = max((post.comment_count or 0) - 1, 0)
    db.commit()
    db.refresh(post)
    return post.comment_count
