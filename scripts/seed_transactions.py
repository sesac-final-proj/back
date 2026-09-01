"""Transaction 시드 스크립트: python -m scripts.seed_transactions

data/*.csv (당근 크롤링 원천 거래 데이터)를 Transaction 테이블에 적재한다.
컬럼 매핑은 docs/ERD.md 4절 참고. 1회성 스크립트라 중복 적재 방지는 하지
않는다 — 재실행 전 운영자가 판단.
"""
import csv
import glob
from datetime import date

from app.core.db import SessionLocal
from app.models.region import Region
from app.models.transaction import Transaction


def _parse_price(raw: str) -> int | None:
    raw = raw.strip()
    if not raw or raw == "무료나눔":
        return None
    return int(raw.replace(",", "").replace("원", ""))


def _parse_manner_temp(raw: str) -> float | None:
    raw = raw.strip()
    return float(raw.replace("℃", "")) if raw else None


def seed(csv_glob: str = "data/*.csv") -> int:
    db = SessionLocal()
    count = 0
    try:
        region_by_name = {r.dong_name: r.id for r in db.query(Region).all()}
        for path in glob.glob(csv_glob):
            with open(path, encoding="utf-8-sig", newline="") as f:
                for row in csv.DictReader(f):
                    db.add(
                        Transaction(
                            product_title=row["제목"],
                            search_keyword=row["검색어"] or None,
                            category=row["카테고리"],
                            detail_category=row["상세카테고리"] or None,
                            price=_parse_price(row["가격"]),
                            region_id=region_by_name.get(row["지역"].strip()),
                            status=row["상태"],
                            trade_place=row["거래희망장소"] or None,
                            description=row["상세설명"] or None,
                            seller_nickname=row["판매자닉네임"] or None,
                            seller_manner_temp=_parse_manner_temp(row["매너온도"]),
                            chat_count=int(row["채팅수"]),
                            interest_count=int(row["관심수"]),
                            view_count=int(row["조회수"]),
                            listed_at=date.fromisoformat(row["등록시각"].strip()),
                        )
                    )
                    count += 1
        db.commit()
    finally:
        db.close()
    return count


if __name__ == "__main__":
    n = seed()
    print(f"{n}건 적재 완료")
