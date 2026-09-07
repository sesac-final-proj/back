"""공통 인프라(비밀번호 해시, JWT, 인증 Dependency) 자가 점검.

pytest 없이 python -m tests.test_common_infra 로 바로 실행 가능.
실제 개발 DB에 임시 유저를 만들었다가 끝나면 지운다.
"""

from datetime import datetime, timedelta, timezone

import jwt as pyjwt
from fastapi import HTTPException

from app.api.v1.auth import service as auth_service
from app.core import redis_client
from app.core.config import settings
from app.core.db import SessionLocal
from app.core.deps import get_current_user, require_admin
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.user import User, UserRole


def check_password_hashing():
    hashed = hash_password("s3cret-pass")
    assert hashed != "s3cret-pass"
    assert verify_password("s3cret-pass", hashed)
    assert not verify_password("wrong-pass", hashed)


def check_token_roundtrip():
    access = create_access_token(subject="42")
    payload = decode_token(access)
    assert payload["sub"] == "42"
    assert payload["type"] == "access"

    refresh = create_refresh_token(subject="42")
    assert decode_token(refresh)["type"] == "refresh"

    try:
        decode_token(access + "tampered")
        raise AssertionError("변조된 토큰이 통과하면 안 된다")
    except pyjwt.PyJWTError:
        pass


def check_auth_dependency():
    db = SessionLocal()
    user = User(
        email="__common_infra_selfcheck__@example.com",
        password_hash=hash_password("x"),
        nickname="selfcheck",
        role=UserRole.USER,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    try:
        access_token = create_access_token(subject=str(user.id))
        resolved = get_current_user(token=access_token, db=db)
        assert resolved.id == user.id

        # 잘못된 토큰 -> 401
        try:
            get_current_user(token="garbage", db=db)
            raise AssertionError("잘못된 토큰이 통과하면 안 된다")
        except HTTPException as e:
            assert e.status_code == 401

        # refresh 토큰으로 접근 -> 401 (access 전용)
        refresh_token = create_refresh_token(subject=str(user.id))
        try:
            get_current_user(token=refresh_token, db=db)
            raise AssertionError("refresh 토큰으로 인증 통과하면 안 된다")
        except HTTPException as e:
            assert e.status_code == 401

        # 일반 유저가 require_admin 호출 -> 403
        try:
            require_admin(user=resolved)
            raise AssertionError("일반 유저가 admin 통과하면 안 된다")
        except HTTPException as e:
            assert e.status_code == 403

        user.role = UserRole.ADMIN
        db.commit()
        db.refresh(user)
        assert require_admin(user=user).id == user.id
    finally:
        db.delete(user)
        db.commit()
        db.close()


def check_refresh_token_5_week_expiry():
    """로그인 유지기간 5주(REFRESH_TOKEN_EXPIRE_DAYS=35) 정책이 실제로 걸려있는지 점검.

    JWT exp와 Redis TTL 둘 다 이 값을 따라가는데, 한쪽만 고치면 "5주 전에 조용히
    로그아웃"되거나 "5주 지나도 refresh가 계속 통과"하는 버그가 되므로 둘 다 확인한다.
    """
    assert settings.REFRESH_TOKEN_EXPIRE_DAYS == 35, "로그인 유지기간 정책(5주)이 바뀌었으면 이 값도 같이 확인"

    # 이미 만료된 refresh 토큰 — decode_token과 auth_service.refresh() 둘 다 거부해야 한다.
    expired_payload = {
        "sub": "999999",
        "role": "user",
        "provider": "local",
        "type": "refresh",
        "jti": "expired-selfcheck-jti",
        "iat": datetime.now(timezone.utc) - timedelta(days=36),
        "exp": datetime.now(timezone.utc) - timedelta(days=1),
    }
    expired_token = pyjwt.encode(expired_payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)

    try:
        decode_token(expired_token)
        raise AssertionError("만료된 토큰이 decode를 통과하면 안 된다")
    except pyjwt.ExpiredSignatureError:
        pass

    db = SessionLocal()
    try:
        try:
            auth_service.refresh(db, expired_token)
            raise AssertionError("만료된 refresh 토큰으로 재발급되면 안 된다(로그아웃 상태 유지)")
        except HTTPException as e:
            assert e.status_code == 401
    finally:
        db.close()

    # 정상 발급된 refresh 토큰은 Redis TTL도 정확히 5주여야 한다.
    refresh_token = create_refresh_token(subject="42")
    payload = decode_token(refresh_token)
    ttl_seconds = int(payload["exp"] - datetime.now(timezone.utc).timestamp())
    redis_client.save_refresh_token(payload["jti"], 42, ttl_seconds)
    try:
        actual_ttl = redis_client._client().ttl(f"refresh_token:{payload['jti']}")
        expected_ttl = settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400
        assert abs(actual_ttl - expected_ttl) < 5, f"Redis TTL({actual_ttl}s)이 설정값({expected_ttl}s)과 어긋난다"
        assert redis_client.is_refresh_token_valid(payload["jti"])
    finally:
        redis_client.revoke_refresh_token(payload["jti"])
    assert not redis_client.is_refresh_token_valid(payload["jti"])


def main():
    check_password_hashing()
    check_token_roundtrip()
    check_auth_dependency()
    check_refresh_token_5_week_expiry()
    print("common-infra self-check OK")


if __name__ == "__main__":
    main()
