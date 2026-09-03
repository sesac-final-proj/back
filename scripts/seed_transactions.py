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


def _parse_price(row: dict) -> int | None:
    # "가격원" 컬럼(정수 문자열, 무료나눔은 "0")이 있으면 그걸 우선 신뢰한다 —
    # "111만 1,111원"처럼 "가격" 원문 텍스트만으로는 못 푸는 표기가 있어서다.
    gawon = row.get("가격원", "").strip()
    if gawon:
        value = int(gawon)
        return None if value == 0 else value

    raw = row["가격"].strip()
    if not raw or raw == "무료나눔":
        return None
    return int(raw.replace(",", "").replace("원", ""))


def _parse_manner_temp(raw: str) -> float | None:
    raw = raw.strip()
    return float(raw.replace("℃", "")) if raw else None


def _parse_count(raw: str) -> int:
    # 송파구 CSV엔 채팅수/관심수/조회수가 빈 문자열인 행이 있다(영등포구엔 없었음) — 0으로 취급.
    raw = raw.strip()
    return int(raw) if raw else 0


def _truncate(raw: str | None, max_len: int) -> str | None:
    # 컬럼이 varchar(200)인데 크롤러가 판매자 설명을 통째로 넣은 것 같은 이상치 행이
    # 극소수 있다(송파구 CSV 2건) — 값을 버리는 대신 잘라서 저장.
    if not raw:
        return None
    return raw[:max_len]


def seed(csv_glob: str = "data/*.csv") -> tuple[int, int]:
    db = SessionLocal()
    count = skipped = 0
    try:
        region_by_name = {r.dong_name: r.id for r in db.query(Region).all()}
        for path in glob.glob(csv_glob):
            with open(path, encoding="utf-8-sig", newline="") as f:
                for row in csv.DictReader(f):
                    if not row["등록시각"].strip():
                        # 크롤링이 상세페이지까지 못 긁은 불완전한 행 — listed_at이
                        # NOT NULL이라 날짜를 지어내는 대신 건너뛴다.
                        skipped += 1
                        continue
                    db.add(
                        Transaction(
                            product_title=row["제목"],
                            search_keyword=row["검색어"] or None,
                            category=row["카테고리"],
                            detail_category=row["상세카테고리"] or None,
                            price=_parse_price(row),
                            region_id=region_by_name.get(row["지역"].strip()),
                            status=row["상태"],
                            trade_place=_truncate(row["거래희망장소"], 200),
                            description=row["상세설명"] or None,
                            seller_nickname=row["판매자닉네임"] or None,
                            seller_manner_temp=_parse_manner_temp(row["매너온도"]),
                            chat_count=_parse_count(row["채팅수"]),
                            interest_count=_parse_count(row["관심수"]),
                            view_count=_parse_count(row["조회수"]),
                            listed_at=date.fromisoformat(row["등록시각"].strip()),
                        )
                    )
                    count += 1
        db.commit()
    finally:
        db.close()
    return count, skipped


if __name__ == "__main__":
    n, skipped = seed()
    print(f"{n}건 적재 완료, {skipped}건 등록시각 누락으로 스킵")
