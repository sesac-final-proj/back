from datetime import datetime, timedelta, timezone
from uuid import uuid4

import bcrypt
import jwt

from app.core.config import settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def _create_token(
    subject: str,
    expires_delta: timedelta,
    token_type: str,
    role: str = "user",
    provider: str = "local",
) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "role": role,
        "provider": provider,
        "type": token_type,
        "jti": str(uuid4()),
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def create_access_token(subject: str, role: str = "user", provider: str = "local") -> str:
    return _create_token(
        subject, timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES), "access", role, provider
    )


def create_refresh_token(subject: str, role: str = "user", provider: str = "local") -> str:
    return _create_token(
        subject, timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS), "refresh", role, provider
    )


def decode_token(token: str) -> dict:
    """만료/위조 시 jwt.PyJWTError를 던진다 (호출부에서 401로 변환)."""
    return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
