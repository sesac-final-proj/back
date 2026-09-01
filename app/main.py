import logging
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.auth.router import legacy_router as legacy_auth_router
from app.api.v1.auth.router import router as auth_router
from app.api.v1.chats.router import router as chats_router
from app.api.v1.local.router import router as local_router
from app.api.v1.nicknames.router import router as nicknames_router
from app.api.v1.trades.router import router as trades_router
from app.core.config import settings
from app.core.db import test_connection
from app.core.exceptions import register_exception_handlers

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("app.request")

app = FastAPI(docs_url="/api/docs", redoc_url="/api/redoc", openapi_url="/api/openapi.json")
register_exception_handlers(app)

# 로컬 프론트 개발 서버만 허용. 배포 origin은 나올 때 .env 기반 설정으로 분리.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in settings.FRONTEND_ORIGINS.split(",")
        if origin.strip()
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.monotonic()
    response = await call_next(request)
    duration_ms = (time.monotonic() - start) * 1000
    logger.info(
        "%s %s %s %.1fms", request.method, request.url.path, response.status_code, duration_ms
    )
    return response


app.include_router(trades_router)
app.include_router(chats_router)
app.include_router(local_router)
app.include_router(auth_router)
app.include_router(legacy_auth_router)
app.include_router(nicknames_router)


@app.get("/api")
def read_root():
    return {"message": "Hello, FastAPI"}


@app.get("/api/health/db")
def health_db():
    return {"db_connected": test_connection()}
