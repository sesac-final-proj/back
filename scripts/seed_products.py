"""Product 시드 스크립트: python -m scripts.seed_products

이미 적재된 Transaction(scripts/seed_transactions.py)을 실제 마켓 매물
(Product)로 변환해 중고거래 화면에 보이도록 한다. 원본 크롤링 데이터를
그대로 옮기는 것이라 재파싱하지 않고 Transaction을 그대로 읽는다.
region_id가 없는(매칭 실패) 행은 Product.region_id가 NOT NULL이라
제외한다. 1회성 스크립트라 중복 적재 방지는 하지 않는다 — 재실행 전
운영자가 판단.
"""
from datetime import datetime, time

from app.core.db import SessionLocal
from app.models.product import Product
from app.models.transaction import Transaction

# Transaction.status(크롤링 원문) -> Product.trade_status
STATUS_MAP = {
    "거래중": "SALE",
    "예약중": "RESERVED",
    "거래완료": "SOLD",
    "나눔완료": "SOLD",
}


def seed() -> tuple[int, int]:
    db = SessionLocal()
    inserted = skipped = 0
    try:
        transactions = db.query(Transaction).filter(Transaction.region_id.isnot(None)).all()
        for t in transactions:
            trade_status = STATUS_MAP.get(t.status)
            if trade_status is None:
                skipped += 1
                continue
            db.add(
                Product(
                    title=t.product_title,
                    category=t.category,
                    search_keyword=t.search_keyword,
                    description=t.description,
                    seller_manner_temp=t.seller_manner_temp,
                    desired_price=t.price,
                    region_id=t.region_id,
                    created_by=None,  # 크롤링 원본 데이터 — 우리 서비스 유저 소유 아님
                    trade_status=trade_status,
                    trade_type="FREE" if t.price is None else "SALE",
                    created_at=datetime.combine(t.listed_at, time()),
                )
            )
            inserted += 1
        db.commit()
    finally:
        db.close()
    return inserted, skipped


if __name__ == "__main__":
    inserted, skipped = seed()
    print(f"{inserted}건 적재 완료, {skipped}건 상태값 미매핑으로 스킵")
