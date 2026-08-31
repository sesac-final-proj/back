import logging
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.chats.router import router as chats_router
from app.api.v1.trades.router import router as trades_router
from app.core.db import test_connection
from app.core.exceptions import register_exception_handlers

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("app.request")

app = FastAPI()
register_exception_handlers(app)

# 로컬 프론트 개발 서버만 허용. 배포 origin은 나올 때 .env 기반 설정으로 분리.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
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

# 나머지 EPIC 라우터는 각 feat/{epic} 브랜치에서 완성되는 대로 여기에 include:
# from app.api.v1.auth.router import router as auth_router
# app.include_router(auth_router)


@app.get("/")
def read_root():
    return {"message": "Hello, FastAPI"}


@app.get("/health/db")
def health_db():
    return {"db_connected": test_connection()}
