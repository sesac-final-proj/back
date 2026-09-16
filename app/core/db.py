from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings

# 세션풀 슬롯 하나만 있는 pgbouncer 세션모드(5432)로 실수로 다시 돌아가더라도
# 프로세스 하나가 그 전체(15개)를 혼자 다 못 쓰게 여기서도 방어적으로 작게 잡아둔다
# — 여러 로컬 개발 서버 + 운영 서버가 같은 DB를 공유하는 지금 상황에 맞춤.
engine = create_engine(settings.database_url, pool_pre_ping=True, pool_size=3, max_overflow=2)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_connection() -> bool:
    with engine.connect() as conn:
        return conn.execute(text("SELECT 1")).scalar() == 1
