"""가격예측 모델(analyzer/ 파이프라인) 산출물을 DB에 적재.

python -m scripts.seed_price_model_data [--source-dir PATH]

analyzer/outputs/(metrics.json, viz_전처리완료.csv, predictions_sample_*.csv,
platform_price_comparison.csv, platform_price_tests.csv, gmm_price_clusters.csv)를
읽어 price_model_* 테이블에 적재한다. 재학습마다 통째로 다시 뽑는 배치 산출물이라
증분 갱신 대신 테이블별로 전량 truncate 후 재적재한다(멱등 — 몇 번을 다시 돌려도
결과가 같음).

--source-dir 기본값은 이 리포지토리와 analyzer/가 형제 디렉터리로 나란히 있다는
전제(현재 모노레포 레이아웃)의 상대경로다. 두 리포지토리가 완전히 분리 배포되면
그때 가서 산출물을 이 스크립트가 읽을 수 있는 고정 경로에 복사해두거나 인자로 넘기면 된다.
"""
import argparse
import csv
import json
from pathlib import Path

from app.core.db import SessionLocal
from app.models.price_model import (
    PriceCluster,
    PriceModelListing,
    PriceModelMetric,
    PricePlatformComparison,
    PricePlatformTest,
    PricePrediction,
)

DEFAULT_SOURCE_DIR = Path(__file__).resolve().parents[2] / "analyzer" / "outputs"


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        print(f"  스킵 — 파일 없음: {path}")
        return []
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _to_int(raw: str) -> int:
    return int(float(raw))


def seed_metrics(db, source_dir: Path) -> int:
    path = source_dir / "metrics.json"
    if not path.exists():
        print(f"  스킵 — 파일 없음: {path}")
        return 0
    data = json.loads(path.read_text(encoding="utf-8"))

    db.query(PriceModelMetric).delete()
    count = 0
    for feature_set, models in data.items():
        for model_key, metric in models.items():
            core_keys = {"label", "rmse", "mae", "mape", "r2", "hit10", "hit20"}
            db.add(
                PriceModelMetric(
                    feature_set=feature_set,
                    model_key=model_key,
                    label=metric["label"],
                    rmse=metric["rmse"],
                    mae=metric["mae"],
                    mape=metric["mape"],
                    r2=metric["r2"],
                    hit10=metric["hit10"],
                    hit20=metric["hit20"],
                    extra={k: v for k, v in metric.items() if k not in core_keys} or None,
                )
            )
            count += 1
    return count


def seed_listings(db, source_dir: Path) -> int:
    rows = _read_csv(source_dir / "viz_전처리완료.csv")
    db.query(PriceModelListing).delete()
    for row in rows:
        db.add(
            PriceModelListing(
                category=row["카테고리"],
                detail_type=row["세부유형"],
                gu=row["구"],
                condition=row["상품상태"],
                status=row["상태"],
                chat_count=_to_int(row["채팅수"]),
                interest_count=_to_int(row["관심수"]),
                view_count=float(row["조회수"]),
                manner_temp=float(row["매너온도_수치"]),
                title_length=_to_int(row["제목_길이"]),
                days_since_listed=_to_int(row["등록_경과일"]),
                category_detail_median_price=float(row["카테고리_세부유형_중앙가"]),
                price=_to_int(row["가격원"]),
                price_log=float(row["가격원_log"]),
                title=row["제목"],
            )
        )
    return len(rows)


def seed_predictions(db, source_dir: Path) -> int:
    db.query(PricePrediction).delete()
    total = 0
    for feature_set in ("full", "no_leak_prone"):
        rows = _read_csv(source_dir / f"predictions_sample_{feature_set}.csv")
        for row in rows:
            db.add(
                PricePrediction(
                    feature_set=feature_set,
                    category=row["카테고리"],
                    detail_type=row["세부유형"],
                    title=row["제목"],
                    actual_price=_to_int(row["실제가격"]),
                    predicted_price=_to_int(row["예측가격"]),
                    error_rate=float(row["오차율"]),
                )
            )
            total += 1
    return total


def seed_platform_comparisons(db, source_dir: Path) -> int:
    rows = _read_csv(source_dir / "platform_price_comparison.csv")
    db.query(PricePlatformComparison).delete()
    for row in rows:
        db.add(
            PricePlatformComparison(
                category=row["카테고리"],
                platform=row["플랫폼"],
                sample_count=_to_int(row["n"]),
                mean_price=float(row["평균"]),
                median_price=float(row["중앙값"]),
                std_price=float(row["표준편차"]),
                p25_price=float(row["p25"]),
                p75_price=float(row["p75"]),
            )
        )
    return len(rows)


def seed_platform_tests(db, source_dir: Path) -> int:
    rows = _read_csv(source_dir / "platform_price_tests.csv")
    db.query(PricePlatformTest).delete()
    for row in rows:
        db.add(
            PricePlatformTest(
                category=row["카테고리"],
                platform_a=row["플랫폼A"],
                platform_b=row["플랫폼B"],
                median_a=float(row["A_중앙값"]),
                median_b=float(row["B_중앙값"]),
                diff_pct=float(row["B가_A대비_차이(%)"]),
                p_value=float(row["p-value"]),
                significant=row["유의(p<0.05)"].strip().lower() == "true",
            )
        )
    return len(rows)


def seed_clusters(db, source_dir: Path) -> int:
    rows = _read_csv(source_dir / "gmm_price_clusters.csv")
    db.query(PriceCluster).delete()
    for row in rows:
        db.add(
            PriceCluster(
                category=row["카테고리"],
                price_band=row["가격대"],
                share=float(row["비중"]),
                median_price=float(row["중앙값(원)"]),
                range_low=float(row["대략범위_저(원)"]),
                range_high=float(row["대략범위_고(원)"]),
                sample_count=_to_int(row["건수"]),
            )
        )
    return len(rows)


def seed(source_dir: Path) -> None:
    db = SessionLocal()
    try:
        print(f"metrics: {seed_metrics(db, source_dir)}건")
        print(f"listings: {seed_listings(db, source_dir)}건")
        print(f"predictions: {seed_predictions(db, source_dir)}건")
        print(f"platform_comparisons: {seed_platform_comparisons(db, source_dir)}건")
        print(f"platform_tests: {seed_platform_tests(db, source_dir)}건")
        print(f"clusters: {seed_clusters(db, source_dir)}건")
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=DEFAULT_SOURCE_DIR,
        help=f"analyzer 산출물 디렉터리 (기본값: {DEFAULT_SOURCE_DIR})",
    )
    args = parser.parse_args()
    seed(args.source_dir)
    print("price-model 데이터 적재 완료")
