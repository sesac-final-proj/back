"""PriceComparisonSampleItem.interest_count 자가 점검.

python -m tests.test_price_comparison_interest 로 실행. 읽기 전용 —
scripts/seed_price_distribution_data.py로 이미 적재된 스냅샷을 그대로 조회만
한다(데이터 생성/삭제 없음).
"""

from app.api.v1.admin import service as admin_service
from app.core.db import SessionLocal
from app.models.price_distribution import PriceListingSample


def main():
    db = SessionLocal()
    try:
        category = db.query(PriceListingSample.category).filter(PriceListingSample.category == "전체").first()
        assert category is not None, "seed_price_distribution_data.py를 먼저 돌려야 한다"

        result = admin_service.get_price_comparison_samples(db, "전체", None, sample=10_000)
        assert result.samples, "표본이 비어있으면 안 된다"
        assert all(hasattr(s, "interest_count") for s in result.samples)
        assert any(s.interest_count > 0 for s in result.samples), "관심수가 전부 0이면 CSV 컬럼명이 안 맞을 수 있다"

        # DB 원본과 대조 — 스키마 변환 과정에서 값이 안 새는지 확인.
        row = db.query(PriceListingSample).filter(PriceListingSample.category == "전체").first()
        matching = [s for s in result.samples if s.gu == row.gu and s.price == row.price]
        assert matching, "DB 행이 서비스 응답에도 있어야 한다(표본 추출로 빠졌을 수도 있어 존재 여부만 느슨하게 확인)"

        # gu 필터도 interest_count를 그대로 태워 보내는지.
        gu_filtered = admin_service.get_price_comparison_samples(db, "전체", row.gu, sample=10_000)
        assert all(s.gu == row.gu for s in gu_filtered.samples)
        assert any(s.price == row.price and s.interest_count == row.interest_count for s in gu_filtered.samples)

        print("OK: price comparison interest_count self-check passed")
    finally:
        db.close()


if __name__ == "__main__":
    main()
