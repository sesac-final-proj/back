from fastapi import FastAPI

from db import test_connection

app = FastAPI()


@app.get("/")
def read_root():
    return {"message": "Hello, FastAPI"}


@app.get("/health/db")
def health_db():
    return {"db_connected": test_connection()}
