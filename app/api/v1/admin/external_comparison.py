"""Read-only, source-bound platform snapshot; no generated or AI price estimates."""
import csv
import re
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path
from statistics import mean, pstdev

from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.api.v1.admin import schema
from app.models.price_model import PricePlatformComparison

DATA_DIR = Path(__file__).resolve().parents[4] / "data"
SOURCES = (("당근", "daangn_영등포구.csv"), ("번개장터", "elecmart_conformed.csv"),
           ("중고나라", "joonggonara_conformed.csv"))
CAVEAT = "수집 매물 등록가이며 체결가·시장 점유율이 아닙니다. 모델·상태·지역·게시 기간이 다를 수 있습니다."
POSITIVE_TERMS = ("미개봉", "새상품", "새제품", "최상", "깨끗", "정품", "풀박스", "보증", "거의 새것")
NEGATIVE_TERMS = ("하자", "고장", "파손", "흠집", "사용감", "수리", "누락", "불량", "부품용")


def percentile(values: list[int], fraction: float) -> float:
    position = (len(values) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(values) - 1)
    return values[lower] + (values[upper] - values[lower]) * (position - lower)


def listing_sentiment(title: str) -> tuple[str, list[str], list[str]]:
    text = title.casefold()
    positive = [term for term in POSITIVE_TERMS if term in text]
    negative = [term for term in NEGATIVE_TERMS if term in text]
    tone = "positive" if len(positive) > len(negative) else "negative" if len(negative) > len(positive) else "neutral"
    return tone, positive, negative


def summarize_sentiment(records: list[dict]) -> dict:
    grouped = defaultdict(lambda: {"total": 0, "positive": 0, "neutral": 0, "negative": 0,
                                  "positive_terms": Counter(), "negative_terms": Counter()})
    for record in records:
        tone, positive, negative = listing_sentiment(record["title"])
        for key in (record["platform"], f'{record["platform"]}|{record["category"]}'):
            group = grouped[key]
            group["total"] += 1
            group[tone] += 1
            group["positive_terms"].update(positive)
            group["negative_terms"].update(negative)

    def serialize(key: str, values: dict) -> dict:
        platform, _, category = key.partition("|")
        total = values["total"]
        return {"platform": platform, "category": category or None, "total": total,
                "positive": values["positive"], "neutral": values["neutral"], "negative": values["negative"],
                "score": round((values["positive"] - values["negative"]) * 100 / total, 1) if total else 0,
                "top_positive_terms": [term for term, _ in values["positive_terms"].most_common(5)],
                "top_negative_terms": [term for term, _ in values["negative_terms"].most_common(5)]}

    return {"method": "제목의 상품 상태 표현을 고정 사전으로 분류한 규칙 기반 분석",
            "unit": "수집 매물 제목", "analyzed_count": len(records),
            "platforms": [serialize(key, grouped[key]) for key in sorted(grouped) if "|" not in key],
            "categories": [serialize(key, grouped[key]) for key in sorted(grouped) if "|" in key]}


@lru_cache(maxsize=2)
def load_csv_snapshot(directory: str, versions: tuple) -> dict:
    groups = defaultdict(list)
    sources = []
    sentiment_records = []
    for platform, filename in SOURCES:
        path = Path(directory) / filename
        if not path.is_file():
            sources.append({"platform": platform, "file": filename, "missing": True})
            continue
        seen = set()
        total = duplicates = excluded = 0
        with path.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                total += 1
                identity = tuple(sorted(row.items()))
                if identity in seen:
                    duplicates += 1
                    continue
                seen.add(identity)
                price = re.fullmatch(r"([0-9][0-9,]*)\s*원?", (row.get("가격") or "").strip())
                category = (row.get("카테고리") or "").strip()
                value = int(price.group(1).replace(",", "")) if price else 0
                if not category or value <= 0:
                    excluded += 1
                    continue
                groups[(category, platform)].append(value)
                sentiment_records.append({"platform": platform, "category": category,
                                          "title": (row.get("제목") or "").strip()})
        sources.append({"platform": platform, "file": filename, "rows": total,
                        "duplicates": duplicates, "excluded": excluded, "accepted": total - duplicates - excluded})
    items = []
    for (category, platform), prices in sorted(groups.items()):
        prices.sort()
        items.append({"category": category, "platform": platform, "sample_count": len(prices),
                      "mean_price": mean(prices), "median_price": percentile(prices, .5),
                      "std_price": pstdev(prices), "p25_price": percentile(prices, .25),
                      "p75_price": percentile(prices, .75)})
    return {"items": items, "sources": sources, "sentiment": summarize_sentiment(sentiment_records),
            "period": "저장 CSV 스냅샷 · 공통 수집 기간 미확인",
            "source": "data/ 개별 플랫폼 CSV 3종 · 당근 영등포구 표본",
            "caveat": CAVEAT + " 무료·가격 미상과 완전 중복 행은 제외. 거래 상태 전체 포함. 통합 CSV는 중복 합산하지 않습니다."}


def get_external_comparison(db: Session) -> dict:
    if inspect(db.get_bind()).has_table(PricePlatformComparison.__tablename__):
        rows = db.query(PricePlatformComparison).order_by(PricePlatformComparison.category, PricePlatformComparison.platform).all()
        if rows:
            snapshot = load_csv_snapshot(str(DATA_DIR), tuple((name, (DATA_DIR / name).stat().st_mtime_ns,
                                            (DATA_DIR / name).stat().st_size) for _, name in SOURCES if (DATA_DIR / name).is_file()))
            return {"items": [schema.PricePlatformComparisonItem.model_validate(row) for row in rows],
                    "sources": [], "sentiment": snapshot["sentiment"], "period": "수집 기간 메타데이터 미제공",
                    "source": "price_platform_comparisons · DB 집계", "caveat": CAVEAT}
    versions = tuple((name, (DATA_DIR / name).stat().st_mtime_ns, (DATA_DIR / name).stat().st_size)
                     for _, name in SOURCES if (DATA_DIR / name).is_file())
    return load_csv_snapshot(str(DATA_DIR), versions)
