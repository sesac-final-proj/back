"""당근마켓 크롤링 분석(crawling_Data 세션) 전처리 산출물을 DB에 적재.

python -m scripts.seed_price_distribution_data [--source PATH]

data/viz_전처리완료.csv(카테고리/세부유형/구/상품상태/상태/채팅수/관심수/조회수/
매너온도_수치/제목_길이/등록_경과일/카테고리_세부유형_중앙가/가격원/가격원_log/제목,
15열)를 읽어 price_category_summaries / price_region_stats /
price_detail_type_stats / price_listing_samples 4개 테이블에 적재한다.

price_dong_stats(동네 시세지도)는 이 파일이 안 다룬다 — viz_전처리완료.csv엔 "동"
컬럼이 없어서, data/daangn_{구}.csv 원본 3개(지역=동 컬럼 있음)를 따로 읽어 채운다
(raw_gu_rows/seed_dong_stats 참고). 두 소스가 다른 전처리를 거치므로 집계치가
카테고리 요약과 완전히 똑같진 않을 수 있다 — 동 단위 시세 "감"을 보여주는 용도.

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
    PriceDongStat,
    PriceListingSample,
    PriceRegionStat,
)

DEFAULT_SOURCE = Path(__file__).resolve().parents[1] / "data" / "viz_전처리완료.csv"
DATA_DIR = Path(__file__).resolve().parents[1] / "data"
# 동 단위 시세지도 전용 — 원본 크롤링 파일 3개(구별). viz_전처리완료.csv와 달리
# "지역" 컬럼에 동 이름이 그대로 있다.
RAW_GU_SOURCES = {
    "영등포구": DATA_DIR / "daangn_영등포구.csv",
    "송파구": DATA_DIR / "daangn_송파구.csv",
    "노원구": DATA_DIR / "daangn_노원구.csv",
}

RECENT_TREND_DAYS = 180  # 최근/이전 median 비교 기준
MIN_TREND_SAMPLES = 10  # 그룹당 이 미만이면 price_trend_pct는 NULL
MIN_DETAIL_TYPE_SAMPLES = 10  # (카테고리,세부유형,구) 조합 최소 표본
MIN_DONG_SAMPLES = 10  # (카테고리,구,동) 조합 최소 표본 — 세부유형과 같은 기준
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


def _parse_price(row: dict[str, str]) -> int | None:
    """원본 크롤링 파일 3개가 서로 다르게 채워져 있다 — 노원구 파일은 "가격원"이
    전부 빈 문자열이고 대신 "가격"에 "21,000원" 형식으로만 들어있다(실제로 확인함).
    "가격원"이 유효하면 그대로 쓰고, 아니면 "가격"에서 숫자만 뽑아 쓴다."""
    raw = (row.get("가격원") or "").strip()
    if raw.isdigit():
        return int(raw)
    fallback = (row.get("가격") or "").strip()
    digits = "".join(ch for ch in fallback if ch.isdigit())
    return int(digits) if digits else None


def _read_raw_gu_rows() -> list[dict[str, str]]:
    """동 단위 시세지도용 — data/daangn_{구}.csv 원본 3개를 합쳐서 읽는다.
    "지역" 컬럼이 그대로 동 이름이고(파일 자체가 구 하나로 스코프됨), 구는
    RAW_GU_SOURCES 키에서 채워 넣는다(원본 파일엔 구 컬럼이 없음)."""
    rows: list[dict[str, str]] = []
    for gu, path in RAW_GU_SOURCES.items():
        if not path.exists():
            continue
        with path.open(encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                price = _parse_price(r)
                dong = (r.get("지역") or "").strip()
                if price is None or not dong or not r.get("카테고리"):
                    continue
                rows.append({"카테고리": r["카테고리"], "구": gu, "동": dong, "가격": price})
    return rows


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
        completed = sum(1 for r in crows if r["상태"] == "거래완료")
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
                completion_rate=round(completed / len(crows) * 100, 1),
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
        mean_price = st.mean(prices)
        std_price = st.pstdev(prices)
        completed = sum(1 for r in grows if r["상태"] == "거래완료")
        span_days = max(int(r["등록_경과일"]) for r in grows) or 1
        listings_per_month = len(grows) / (span_days / 30)
        db.add(
            PriceRegionStat(
                category=category,
                gu=gu,
                sample_count=len(grows),
                median_price=st.median(prices),
                completion_rate=round(completed / len(grows) * 100, 1),
                avg_manner_temp=round(st.mean(float(r["매너온도_수치"]) for r in grows), 1),
                cv_price=round(std_price / mean_price * 100, 1) if mean_price else 0.0,
                frequency_grade=_grade(listings_per_month),
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


def seed_dong_stats(db) -> int:
    """동네 시세지도 — 카테고리별로 상위 3% 가격 이상치를 뺀 뒤(다른 테이블과 동일
    기준), 그 카테고리의 중앙값/1·3분위를 구해서 동마다 median_price/dev_pct(카테고리
    중앙값 대비 편차%)/within_below_above_pct(1~3분위 안/아래/위 비중)를 계산한다."""
    db.query(PriceDongStat).delete()
    raw_rows = _read_raw_gu_rows()
    count = 0
    for category, crows in _group_by_category(raw_rows).items():
        prices = sorted(r["가격"] for r in crows)
        cutoff = prices[int(len(prices) * OUTLIER_TRIM_PCT)]
        trimmed = [r for r in crows if r["가격"] <= cutoff]
        if len(trimmed) < 2:
            continue
        trimmed_prices = sorted(r["가격"] for r in trimmed)
        q1, category_median, q3 = st.quantiles(trimmed_prices, n=4)

        by_dong: dict[tuple[str, str], list[int]] = {}
        for r in trimmed:
            by_dong.setdefault((r["구"], r["동"]), []).append(r["가격"])

        for (gu, dong), dong_prices in by_dong.items():
            if len(dong_prices) < MIN_DONG_SAMPLES:
                continue
            below = sum(1 for p in dong_prices if p < q1)
            above = sum(1 for p in dong_prices if p > q3)
            within = len(dong_prices) - below - above
            dong_median = st.median(dong_prices)
            db.add(
                PriceDongStat(
                    category=category,
                    gu=gu,
                    dong=dong,
                    sample_count=len(dong_prices),
                    median_price=dong_median,
                    within_pct=round(within / len(dong_prices) * 100, 1),
                    below_pct=round(below / len(dong_prices) * 100, 1),
                    above_pct=round(above / len(dong_prices) * 100, 1),
                    dev_pct=round((dong_median - category_median) / category_median * 100, 1) if category_median else 0.0,
                )
            )
            count += 1
    return count


def seed(source: Path) -> None:
    rows = _read_rows(source)
    db = SessionLocal()
    try:
        print(f"카테고리요약: {seed_category_summaries(db, rows)}건")
        print(f"지역별통계: {seed_region_stats(db, rows)}건")
        print(f"세부유형별통계: {seed_detail_type_stats(db, rows)}건")
        print(f"매물표본: {seed_listing_samples(db, rows)}건")
        print(f"동네시세: {seed_dong_stats(db)}건")
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
