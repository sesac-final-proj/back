"""PriceComparisonSampleItem.interest_count / PriceComparisonCategoryItem.completion_rate 자가 점검.

python -m tests.test_price_comparison_interest 로 실행. 읽기 전용 —
scripts/seed_price_distribution_data.py로 이미 적재된 스냅샷을 그대로 조회만
한다(데이터 생성/삭제 없음).
"""

from app.api.v1.admin import service as admin_service
from app.core.db import SessionLocal
from app.models.price_distribution import PriceCategorySummary, PriceListingSample, PriceRegionStat


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

        # completion_rate — DB 값과 오버뷰 응답이 일치하는지, 범위가 0~100인지만 확인
        # (실제 계산은 seed 스크립트 책임 — 여기선 스키마 왕복만 검증).
        overview = admin_service.get_price_comparison_overview(db)
        assert overview.categories, "카테고리 요약이 비어있으면 안 된다"
        for item in overview.categories:
            assert 0 <= item.completion_rate <= 100, f"{item.category} completion_rate 범위 이상: {item.completion_rate}"
        by_category = {r.category: r for r in db.query(PriceCategorySummary).all()}
        for item in overview.categories:
            assert item.completion_rate == by_category[item.category].completion_rate

        # 구별 cv_price/frequency_grade — 응답 필드 존재 + DB와 일치하는지.
        assert overview.regions, "구별 통계가 비어있으면 안 된다"
        by_region = {(r.category, r.gu): r for r in db.query(PriceRegionStat).all()}
        for item in overview.regions:
            row = by_region[(item.category, item.gu)]
            assert item.cv_price == row.cv_price
            assert item.frequency_grade == row.frequency_grade
            assert item.frequency_grade in ("S", "A", "B", "C")

        print("OK: price comparison interest_count/completion_rate/region-grade self-check passed")
    finally:
        db.close()


if __name__ == "__main__":
    main()
