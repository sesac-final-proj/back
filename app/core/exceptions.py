import logging

from fastapi import status
from fastapi.exceptions import RequestValidationError
from fastapi.requests import Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import settings

logger = logging.getLogger("app.request")
_ALLOWED_ORIGINS = {origin.strip() for origin in settings.FRONTEND_ORIGINS.split(",") if origin.strip()}


class AppError(Exception):
    status_code: int = status.HTTP_400_BAD_REQUEST
    code: str = "BAD_REQUEST"

    def __init__(self, message: str):
        self.message = message


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "NOT_FOUND"


class PermissionDeniedError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "PERMISSION_DENIED"


def _error_body(code: str, message: str) -> dict:
    return {"code": code, "message": message, "detail": message}


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=_error_body(exc.code, exc.message))


_HTTP_STATUS_CODE = {
    status.HTTP_401_UNAUTHORIZED: "UNAUTHORIZED",
    status.HTTP_403_FORBIDDEN: "PERMISSION_DENIED",
    status.HTTP_404_NOT_FOUND: "NOT_FOUND",
    status.HTTP_409_CONFLICT: "CONFLICT",
}


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    code = _HTTP_STATUS_CODE.get(exc.status_code, "HTTP_ERROR")
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_body(code, str(exc.detail)),
        headers=getattr(exc, "headers", None),
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=_error_body("VALIDATION_ERROR", str(exc.errors())),
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Starlette는 Exception(=500) 핸들러를 ExceptionMiddleware가 아니라 가장 바깥쪽
    # ServerErrorMiddleware로 빼서 실행한다(build_middleware_stack 참고) — CORSMiddleware
    # 보다 바깥이라 이 핸들러가 만든 응답엔 CORSMiddleware가 헤더를 못 붙인다. 그 상태로
    # 나가면 브라우저가 응답을 막아버려서 프론트엔 500 메시지 대신 "Failed to fetch"만
    # 보인다 — 그래서 CORS 헤더를 여기서 직접 붙인다. 실제 예외는 서버 로그에 남기고,
    # 클라이언트에는 내부 정보 노출 없이 일반 메시지만 반환.
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    response = JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=_error_body("INTERNAL_ERROR", "서버 오류가 발생했습니다."),
    )
    origin = request.headers.get("origin")
    if origin in _ALLOWED_ORIGINS:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Vary"] = "Origin"
    return response


def register_exception_handlers(app) -> None:
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
