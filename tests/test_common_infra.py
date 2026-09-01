"""공통 인프라(비밀번호 해시, JWT, 인증 Dependency) 자가 점검.

pytest 없이 python -m tests.test_common_infra 로 바로 실행 가능.
실제 개발 DB에 임시 유저를 만들었다가 끝나면 지운다.
"""

import jwt as pyjwt
from fastapi import HTTPException

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


def main():
    check_password_hashing()
    check_token_roundtrip()
    check_auth_dependency()
    print("common-infra self-check OK")


if __name__ == "__main__":
    main()
