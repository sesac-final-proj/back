"""Refresh token 저장소 (Redis).

키는 JWT의 jti, TTL은 REFRESH_TOKEN_EXPIRE_DAYS — 만료는 Redis가 알아서
처리하므로 별도 expires_at 컬럼/만료 체크가 필요 없다. 키가 있으면
유효, 없으면(자연 만료 또는 로그아웃/로테이션으로 삭제됨) 무효.
"""
from functools import lru_cache

import redis

from app.core.config import settings

_KEY_PREFIX = "refresh_token:"


@lru_cache
def _client() -> redis.Redis:
    return redis.from_url(settings.redis_url, decode_responses=True)


def save_refresh_token(jti: str, user_id: int, ttl_seconds: int) -> None:
    _client().set(f"{_KEY_PREFIX}{jti}", str(user_id), ex=ttl_seconds)


def is_refresh_token_valid(jti: str) -> bool:
    return _client().exists(f"{_KEY_PREFIX}{jti}") == 1


def revoke_refresh_token(jti: str) -> None:
    _client().delete(f"{_KEY_PREFIX}{jti}")
