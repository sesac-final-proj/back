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
