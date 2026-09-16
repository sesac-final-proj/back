import re

from app.api.v1.nicknames.errors import (
    NICKNAME_CONTAINS_SPACE,
    NICKNAME_FORBIDDEN,
    NICKNAME_INVALID_CHARACTERS,
    NICKNAME_REQUIRED,
    NICKNAME_REQUIRES_KOREAN,
    NICKNAME_TOO_LONG,
    nickname_error,
)
from app.api.v1.nicknames.resources import load_forbidden_words

KOREAN_AND_DIGITS_PATTERN = re.compile(r"^[가-힣0-9]+$")
KOREAN_PATTERN = re.compile(r"[가-힣]")


class NicknameValidator:
    def __init__(self, forbidden_words: list[str] | None = None) -> None:
        self.forbidden_words = forbidden_words if forbidden_words is not None else load_forbidden_words()

    def validate(self, nickname: str) -> str:
        value = nickname.strip()
        if not value:
            raise nickname_error(NICKNAME_REQUIRED)
        if len(value) > 7:
            raise nickname_error(NICKNAME_TOO_LONG)
        if any(char.isspace() for char in nickname):
            raise nickname_error(NICKNAME_CONTAINS_SPACE)
        if not KOREAN_AND_DIGITS_PATTERN.fullmatch(value):
            raise nickname_error(NICKNAME_INVALID_CHARACTERS)
        if not KOREAN_PATTERN.search(value):
            raise nickname_error(NICKNAME_REQUIRES_KOREAN)
        if self.contains_forbidden_word(value):
            raise nickname_error(NICKNAME_FORBIDDEN)
        return value

    def is_valid(self, nickname: str) -> bool:
        try:
            self.validate(nickname)
            return True
        except Exception:
            return False

    def contains_forbidden_word(self, nickname: str) -> bool:
        value = nickname.strip()
        return any(word in value for word in self.forbidden_words)
