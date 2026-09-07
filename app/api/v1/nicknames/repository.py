from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.v1.nicknames.errors import NICKNAME_ALREADY_EXISTS, nickname_error
from app.models.user import User


class NicknameRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def exists(self, nickname: str) -> bool:
        return self.db.scalar(select(User.id).where(User.nickname == nickname)) is not None

    def update_user_nickname(self, user: User, nickname: str) -> User:
        user.nickname = nickname
        user.nickname_set = True
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise nickname_error(NICKNAME_ALREADY_EXISTS) from exc
        self.db.refresh(user)
        return user
