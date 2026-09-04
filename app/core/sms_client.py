"""SMS 발송 (Solapi). SOLAPI_API_KEY/SECRET이 없으면 콘솔 로그로 대체한다 —
Solapi 계정을 발급받기 전에도 인증 코드 흐름(생성→저장→검증) 자체는
그대로 테스트할 수 있게 하기 위한 dev fallback.

ponytail: Solapi HMAC-SHA256 서명 방식은 문서 기준으로 구현했지만 실제
계정으로 검증한 적은 없다 — SOLAPI_API_KEY/SECRET을 넣고 나서 한 번은
꼭 실제 발송으로 확인할 것.
"""
import hashlib
import hmac
import json
import logging
import time
import uuid
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.core.config import settings

logger = logging.getLogger("app.sms")

SOLAPI_SEND_URL = "https://api.solapi.com/messages/v4/send"


def _solapi_auth_header() -> str:
    date = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    salt = uuid.uuid4().hex
    signature = hmac.new(
        settings.SOLAPI_API_SECRET.encode(), f"{date}{salt}".encode(), hashlib.sha256
    ).hexdigest()
    return (
        f"HMAC-SHA256 apiKey={settings.SOLAPI_API_KEY}, date={date}, "
        f"salt={salt}, signature={signature}"
    )


def send_sms(phone_number: str, message: str) -> None:
    if not settings.SOLAPI_API_KEY or not settings.SOLAPI_API_SECRET or not settings.SOLAPI_SENDER_NUMBER:
        # dev fallback: 실제 발송 대신 로그로 — 인증 코드를 서버 로그에서 확인해 테스트한다.
        logger.warning("SOLAPI 미설정 — SMS 대신 로그로 대체: to=%s message=%s", phone_number, message)
        return

    body = json.dumps(
        {"message": {"to": phone_number, "from": settings.SOLAPI_SENDER_NUMBER, "text": message}}
    ).encode()
    request = Request(
        SOLAPI_SEND_URL,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": _solapi_auth_header(),
        },
    )
    try:
        with urlopen(request, timeout=10) as response:
            response.read()
    except (HTTPError, URLError) as exc:
        logger.error("SMS 발송 실패: to=%s error=%s", phone_number, exc)
        raise
