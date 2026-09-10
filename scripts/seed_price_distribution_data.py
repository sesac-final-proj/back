"""당근마켓 크롤링 분석(crawling_Data 세션) 전처리 산출물을 DB에 적재.

python -m scripts.seed_price_distribution_data [--source PATH]

data/viz_전처리완료.csv(카테고리/세부유형/구/상품상태/상태/채팅수/관심수/조회수/
매너온도_수치/제목_길이/등록_경과일/카테고리_세부유형_중앙가/가격원/가격원_log/제목,
15열)를 읽어 price_category_summaries / price_region_stats /
price_detail_type_stats / price_listing_samples 4개 테이블에 적재한다.

이 파일에는 "동(dong)" 컬럼이 없어 price_dong_stats는 이 스크립트로 채우지 않는다
(동네 시세지도는 별도 파이프라인 산출물 — crawling_Data/data_/dong_map.html 참고).

재학습마다 통째로 다시 뽑는 배치 산출물이라 증분 갱신 대신 테이블별로 전량
truncate 후 재적재한다(멱등 — 몇 번을 다시 돌려도 결과가 같음).
"""
import argparse
import csv
import random
import statistics as st
from pathlib import Path

from app.core.db import SessionLocal
from app.models.price_distribution import (
    PriceCategorySummary,
    PriceDetailTypeStat,
    PriceListingSample,
    PriceRegionStat,
)

DEFAULT_SOURCE = Path(__file__).resolve().parents[1] / "data" / "viz_전처리완료.csv"

RECENT_TREND_DAYS = 180  # 최근/이전 median 비교 기준
MIN_TREND_SAMPLES = 10  # 그룹당 이 미만이면 price_trend_pct는 NULL
MIN_DETAIL_TYPE_SAMPLES = 10  # (카테고리,세부유형,구) 조합 최소 표본
MAX_SAMPLES_PER_GU = 600  # 스웜 플롯용 구별 최대 표본수
OUTLIER_TRIM_PCT = 0.97  # 카테고리 기준 상위 3% 가격 이상치 제외

# ponytail: 매물/월 등급 경계값 — 기존 콘솔 프로토타입(가격분포 콘솔 아티팩트)
# 데이터와 맞춰 역산한 값. 실제 등급 분포 보고 조정 필요하면 여기만 바꾸면 됨.
_GRADE_THRESHOLDS = [(100, "S"), (40, "A"), (20, "B")]

ALL_CATEGORIES = "전체"  # 프론트 카테고리 탭 맨 앞에 오는 전체 합산 집계


def _group_by_category(rows: list[dict]) -> dict[str, list[dict]]:
    """실제 카테고리별로 묶고, 전체 합산용 "전체" 그룹도 같이 만든다.

    세부유형별 통계(seed_detail_type_stats)는 여기 안 쓴다 — "청소기 V8"과 "마미케어
    미니"처럼 카테고리가 다르면 세부유형 이름이 겹쳐도 서로 무관한 값이라, 전체 합산이
    의미가 없다(프론트에서 "전체" 선택 시 세부유형 표는 빈 상태로 보임)."""
    by_category: dict[str, list[dict]] = {ALL_CATEGORIES: list(rows)}
    for r in rows:
        by_category.setdefault(r["카테고리"], []).append(r)
    return by_category


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _grade(listings_per_month: float) -> str:
    for threshold, grade in _GRADE_THRESHOLDS:
        if listings_per_month >= threshold:
            return grade
    return "C"


def _trend_pct(rows: list[dict]) -> float | None:
    recent = [int(r["가격원"]) for r in rows if int(r["등록_경과일"]) <= RECENT_TREND_DAYS]
    older = [int(r["가격원"]) for r in rows if int(r["등록_경과일"]) > RECENT_TREND_DAYS]
    if len(recent) < MIN_TREND_SAMPLES or len(older) < MIN_TREND_SAMPLES:
        return None
    older_median = st.median(older)
    if older_median == 0:
        return None
    return round((st.median(recent) - older_median) / older_median * 100, 1)


def seed_category_summaries(db, rows: list[dict]) -> int:
    db.query(PriceCategorySummary).delete()
    by_category = _group_by_category(rows)

    for category, crows in by_category.items():
        prices = [int(r["가격원"]) for r in crows]
        mean_price = st.mean(prices)
        std_price = st.pstdev(prices)
        span_days = max(int(r["등록_경과일"]) for r in crows) or 1
        listings_per_month = len(crows) / (span_days / 30)
        db.add(
            PriceCategorySummary(
                category=category,
                sample_count=len(crows),
                median_price=st.median(prices),
                std_price=std_price,
                cv_price=round(std_price / mean_price * 100, 1) if mean_price else 0.0,
                price_trend_pct=_trend_pct(crows),
                frequency_grade=_grade(listings_per_month),
                listings_per_month=round(listings_per_month, 1),
            )
        )
    return len(by_category)


def seed_region_stats(db, rows: list[dict]) -> int:
    db.query(PriceRegionStat).delete()
    by_group: dict[tuple[str, str], list[dict]] = {}
    for category, crows in _group_by_category(rows).items():
        for r in crows:
            by_group.setdefault((category, r["구"]), []).append(r)

    for (category, gu), grows in by_group.items():
        prices = [int(r["가격원"]) for r in grows]
        completed = sum(1 for r in grows if r["상태"] == "거래완료")
        db.add(
            PriceRegionStat(
                category=category,
                gu=gu,
                sample_count=len(grows),
                median_price=st.median(prices),
                completion_rate=round(completed / len(grows) * 100, 1),
                avg_manner_temp=round(st.mean(float(r["매너온도_수치"]) for r in grows), 1),
            )
        )
    return len(by_group)


def _add_detail_type_rows(db, category: str, detail_type: str, gu: str, rows: list[dict]) -> None:
    if len(rows) < MIN_DETAIL_TYPE_SAMPLES:
        return
    prices = [int(r["가격원"]) for r in rows]
    mean_price = st.mean(prices)
    std_price = st.pstdev(prices)
    db.add(
        PriceDetailTypeStat(
            category=category,
            detail_type=detail_type,
            gu=gu,
            sample_count=len(rows),
            median_price=st.median(prices),
            cv_price=round(std_price / mean_price * 100, 1) if mean_price else 0.0,
        )
    )


def seed_detail_type_stats(db, rows: list[dict]) -> int:
    db.query(PriceDetailTypeStat).delete()
    by_gu: dict[tuple[str, str, str], list[dict]] = {}
    by_all_gu: dict[tuple[str, str], list[dict]] = {}
    for r in rows:
        key = (r["카테고리"], r["세부유형"], r["구"])
        by_gu.setdefault(key, []).append(r)
        by_all_gu.setdefault((r["카테고리"], r["세부유형"]), []).append(r)

    count = 0
    for (category, detail_type, gu), grows in by_gu.items():
        _add_detail_type_rows(db, category, detail_type, gu, grows)
        count += 1
    for (category, detail_type), grows in by_all_gu.items():
        _add_detail_type_rows(db, category, detail_type, "전체", grows)
        count += 1
    return count


def seed_listing_samples(db, rows: list[dict]) -> int:
    db.query(PriceListingSample).delete()
    rng = random.Random(0)

    total = 0
    for category, crows in _group_by_category(rows).items():
        prices = sorted(int(r["가격원"]) for r in crows)
        cutoff = prices[int(len(prices) * OUTLIER_TRIM_PCT)]
        trimmed = [r for r in crows if int(r["가격원"]) <= cutoff]

        by_gu: dict[str, list[dict]] = {}
        for r in trimmed:
            by_gu.setdefault(r["구"], []).append(r)

        for gu, grows in by_gu.items():
            sampled = rng.sample(grows, min(MAX_SAMPLES_PER_GU, len(grows)))
            for r in sampled:
                db.add(
                    PriceListingSample(
                        category=category, gu=gu, price=int(r["가격원"]), interest_count=int(r["관심수"])
                    )
                )
            total += len(sampled)
    return total


def seed(source: Path) -> None:
    rows = _read_rows(source)
    db = SessionLocal()
    try:
        print(f"카테고리요약: {seed_category_summaries(db, rows)}건")
        print(f"지역별통계: {seed_region_stats(db, rows)}건")
        print(f"세부유형별통계: {seed_detail_type_stats(db, rows)}건")
        print(f"매물표본: {seed_listing_samples(db, rows)}건")
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        default=DEFAULT_SOURCE,
        help=f"전처리 완료 CSV 경로 (기본값: {DEFAULT_SOURCE})",
    )
    args = parser.parse_args()
    seed(args.source)
    print("price-distribution 데이터 적재 완료")
