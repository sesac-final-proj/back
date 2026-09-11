import csv

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.v1.admin import external_comparison as comparison


def test_snapshot_uses_three_sources_without_integrated_double_count(tmp_path, monkeypatch):
    fields = ["카테고리", "가격", "제목"]
    for _, name in comparison.SOURCES:
        with (tmp_path / name).open("w", encoding="utf-8-sig", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=fields)
            writer.writeheader()
            for price in ["100원", "200원", "300원", "400원", "400원", "무료", "0원"]:
                writer.writerow({"카테고리": "밥솥", "가격": price, "제목": price})
    (tmp_path / "integrated_market_products.csv").write_text("not an input", encoding="utf-8")
    monkeypatch.setattr(comparison, "DATA_DIR", tmp_path)
    with Session(create_engine("sqlite://")) as db:
        result = comparison.get_external_comparison(db)
    assert len(result["items"]) == 3
    assert {row["platform"] for row in result["items"]} == {"당근", "번개장터", "중고나라"}
    for row in result["items"]:
        assert row["sample_count"] == 4
        assert row["p25_price"] == 175
        assert row["median_price"] == 250
        assert row["p75_price"] == 325
    assert all(source["duplicates"] == 1 and source["excluded"] == 2 for source in result["sources"])


def test_missing_sources_return_empty_not_fabricated(tmp_path, monkeypatch):
    monkeypatch.setattr(comparison, "DATA_DIR", tmp_path)
    with Session(create_engine("sqlite://")) as db:
        result = comparison.get_external_comparison(db)
    assert result["items"] == []
    assert all(source["missing"] for source in result["sources"])


def test_listing_sentiment_exposes_counts_terms_and_method():
    result = comparison.summarize_sentiment([
        {"platform": "당근", "category": "밥솥", "title": "미개봉 정품 밥솥"},
        {"platform": "당근", "category": "밥솥", "title": "사용감과 흠집 있음"},
        {"platform": "당근", "category": "밥솥", "title": "쿠쿠 밥솥 판매"},
        {"platform": "당근", "category": "밥솥", "title": ""},
    ])
    platform = result["platforms"][0]
    assert result["analyzed_count"] == 3
    assert (platform["positive"], platform["neutral"], platform["negative"]) == (1, 1, 1)
    assert platform["score"] == 0
    assert platform["top_positive_terms"][:2] == ["미개봉", "정품"]
    assert platform["top_negative_terms"][:2] == ["흠집", "사용감"]
    assert "규칙 기반" in result["method"]
