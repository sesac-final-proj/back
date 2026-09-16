"""PriceDongStat(동네 시세지도) 자가 점검.

python -m tests.test_price_dong_stats 로 실행. 읽기 전용 —
scripts/seed_price_distribution_data.py로 이미 적재된 스냅샷을 그대로 조회만
한다(데이터 생성/삭제 없음).
"""

from app.api.v1.admin import service as admin_service
from app.models.price_distribution import PriceDongStat
from app.core.db import SessionLocal


def main():
    db = SessionLocal()
    try:
        rows = db.query(PriceDongStat).filter(PriceDongStat.category == "마미케어").all()
        assert rows, "seed_price_distribution_data.py를 먼저 돌려야 한다(동네시세 0건)"

        for r in rows:
            assert r.sample_count >= 10, f"{r.gu} {r.dong} 표본 {r.sample_count}건 — MIN_DONG_SAMPLES 미달인데 남아있다"
            assert r.gu in ("송파구", "영등포구", "노원구"), f"알 수 없는 구: {r.gu}"
            total_pct = round(r.below_pct + r.within_pct + r.above_pct, 0)
            assert 99 <= total_pct <= 101, f"{r.gu} {r.dong} below+within+above가 100%가 아님: {total_pct}"
            assert -100 < r.dev_pct < 300, f"{r.gu} {r.dong} dev_pct 범위 이상: {r.dev_pct}"

        # 실제로 구별로 여러 동이 섞여 있어야 한다(한 구만 있으면 raw CSV 3개 중
        # 일부를 못 읽었다는 뜻).
        gus = {r.gu for r in rows}
        assert gus == {"송파구", "영등포구", "노원구"}, f"구 3개가 다 있어야 하는데: {gus}"

        # 서비스 계층(라우터가 실제로 호출하는 함수) 왕복도 확인.
        response = admin_service.get_price_dong_map(db, "마미케어")
        assert response.category == "마미케어"
        assert len(response.dongs) == len(rows)
        by_key = {(r.gu, r.dong): r for r in rows}
        for item in response.dongs:
            row = by_key[(item.gu, item.dong)]
            assert item.median_price == row.median_price
            assert item.dev_pct == row.dev_pct

        print(f"OK: price dong stats self-check passed ({len(rows)}건, 마미케어 기준)")
    finally:
        db.close()


if __name__ == "__main__":
    main()
