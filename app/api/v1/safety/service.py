from sqlalchemy.orm import Session

from app.api.v1.safety import schema
from app.core.exceptions import AppError, NotFoundError
from app.models.block import UserBlock
from app.models.report import Report
from app.models.user import User


def block_user(db: Session, user: User, target_user_id: int) -> schema.BlockResponse:
    if target_user_id == user.id:
        raise AppError("본인을 차단할 수 없습니다.")
    if db.get(User, target_user_id) is None:
        raise NotFoundError("사용자를 찾을 수 없습니다.")

    existing = (
        db.query(UserBlock)
        .filter(UserBlock.blocker_id == user.id, UserBlock.blocked_id == target_user_id)
        .first()
    )
    if existing is None:
        db.add(UserBlock(blocker_id=user.id, blocked_id=target_user_id))
        db.commit()
    return schema.BlockResponse(blocked=True)


def unblock_user(db: Session, user: User, target_user_id: int) -> schema.BlockResponse:
    db.query(UserBlock).filter(
        UserBlock.blocker_id == user.id, UserBlock.blocked_id == target_user_id
    ).delete()
    db.commit()
    return schema.BlockResponse(blocked=False)


def list_my_blocks(db: Session, user: User, page: int, size: int) -> schema.BlockedUserListResponse:
    query = db.query(UserBlock).filter(UserBlock.blocker_id == user.id)
    total = query.count()
    rows = (
        query.order_by(UserBlock.created_at.desc())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )
    items = [schema.BlockedUserItem.model_validate(r) for r in rows]
    return schema.BlockedUserListResponse(items=items, total=total)


def is_blocked(db: Session, a_id: int, b_id: int) -> bool:
    """둘 중 누가 차단했든(방향 무관) 관계가 있으면 True — 대화는 양방향으로 막는다."""
    return (
        db.query(UserBlock)
        .filter(
            ((UserBlock.blocker_id == a_id) & (UserBlock.blocked_id == b_id))
            | ((UserBlock.blocker_id == b_id) & (UserBlock.blocked_id == a_id))
        )
        .first()
        is not None
    )


def create_report(db: Session, user: User, data: schema.ReportCreateRequest) -> Report:
    report = Report(
        reporter_id=user.id,
        target_type=data.target_type,
        target_id=data.target_id,
        reason=data.reason,
        description=data.description,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report
