"""Redis 기반 단기 저장소 — refresh token 세션 + 휴대폰 인증 코드.

둘 다 "짧은 TTL이 지나면 자동 무효화되는 값"이라는 같은 성격이라 Redis
키-값 + TTL만으로 처리한다. 만료는 Redis가 알아서 하므로 별도 만료 체크가
필요 없다 — 키가 있으면 유효, 없으면(자연 만료 또는 명시적 삭제) 무효.
"""
from functools import lru_cache

import redis

from app.core.config import settings

_REFRESH_PREFIX = "refresh_token:"
_PHONE_CODE_PREFIX = "phone_code:"
PHONE_CODE_TTL_SECONDS = 180  # 3분


@lru_cache
def _client() -> redis.Redis:
    return redis.from_url(settings.redis_url, decode_responses=True)


def save_refresh_token(jti: str, user_id: int, ttl_seconds: int) -> None:
    _client().set(f"{_REFRESH_PREFIX}{jti}", str(user_id), ex=ttl_seconds)


def is_refresh_token_valid(jti: str) -> bool:
    return _client().exists(f"{_REFRESH_PREFIX}{jti}") == 1


def revoke_refresh_token(jti: str) -> None:
    _client().delete(f"{_REFRESH_PREFIX}{jti}")


def save_phone_code(phone_number: str, code: str) -> None:
    _client().set(f"{_PHONE_CODE_PREFIX}{phone_number}", code, ex=PHONE_CODE_TTL_SECONDS)


def check_phone_code(phone_number: str, code: str) -> bool:
    # ponytail: 브루트포스 시도횟수 제한은 없음 — 6자리 코드 + 3분 TTL로 1차 방어만.
    # 악용 신호가 실제로 보이면 그때 시도횟수 카운터 추가.
    saved = _client().get(f"{_PHONE_CODE_PREFIX}{phone_number}")
    return saved is not None and saved == code


def clear_phone_code(phone_number: str) -> None:
    _client().delete(f"{_PHONE_CODE_PREFIX}{phone_number}")
