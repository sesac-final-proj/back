from fastapi import FastAPI

from app.admin.router import router as admin_router
from app.core.db import test_connection
from app.donation.router import router as donation_router
from app.local_info.router import router as local_info_router
from app.member.router import router as member_router
from app.trade.router import router as trade_router

app = FastAPI()

app.include_router(member_router)
app.include_router(trade_router)
app.include_router(local_info_router)
app.include_router(donation_router)
app.include_router(admin_router)


@app.get("/")
def read_root():
    return {"message": "Hello, FastAPI"}


@app.get("/health/db")
def health_db():
    return {"db_connected": test_connection()}
