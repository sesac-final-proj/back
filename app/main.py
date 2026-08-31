from fastapi import FastAPI

from app.core.db import test_connection

app = FastAPI()

# EPIC 라우터는 각 feat/{epic} 브랜치에서 완성되는 대로 여기에 include:
# from app.api.v1.auth.router import router as auth_router
# app.include_router(auth_router)


@app.get("/")
def read_root():
    return {"message": "Hello, FastAPI"}


@app.get("/health/db")
def health_db():
    return {"db_connected": test_connection()}
