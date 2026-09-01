import random

from sqlalchemy.orm import Session

from app.api.v1.nicknames.errors import (
    NICKNAME_ALREADY_EXISTS,
    NICKNAME_AVAILABLE,
    NICKNAME_RECOMMENDATION_FAILED,
    MESSAGES,
    nickname_error,
)
from app.api.v1.nicknames.repository import NicknameRepository
from app.api.v1.nicknames.resources import load_nickname_words
from app.api.v1.nicknames.validator import NicknameValidator
from app.models.user import User


class NicknameService:
    def __init__(self, db: Session) -> None:
        self.repository = NicknameRepository(db)
        self.validator = NicknameValidator()

    def _candidate(self) -> str:
        words = load_nickname_words()
        return f"{random.choice(words['adjectives'])}{random.choice(words['nouns'])}"

    def recommend(self) -> str:
        for _ in range(100):
            nickname = self._candidate()
            if not self.validator.is_valid(nickname):
                continue
            if self.repository.exists(nickname):
                continue
            return nickname
        raise nickname_error(NICKNAME_RECOMMENDATION_FAILED)

    def check_availability(self, nickname: str) -> dict:
        value = self.validator.validate(nickname)
        if self.repository.exists(value):
            raise nickname_error(NICKNAME_ALREADY_EXISTS)
        return {
            "available": True,
            "code": NICKNAME_AVAILABLE,
            "message": MESSAGES[NICKNAME_AVAILABLE],
        }

    def select(self, user: User, nickname: str) -> User:
        value = self.validator.validate(nickname)
        if self.repository.exists(value):
            raise nickname_error(NICKNAME_ALREADY_EXISTS)
        return self.repository.update_user_nickname(user, value)
