"""Read-only analytical checks for local source snapshots and comparison tables.

Run from back: python scripts/validate_admin_comparison.py
"""
import json
import sqlite3
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    snapshot = json.loads((root / "app/data/admin_audience_insights.json").read_text(encoding="utf-8"))
    distributions = snapshot["distributions"]
    checks = {
        "distribution_total_matches_population": sum(row["count"] for row in distributions) == snapshot["population"]["rows"],
        "quartiles_ordered": all(0 <= row["q1"] <= row["median"] <= row["q3"] for row in distributions),
        "source_total_matches_population": sum(row["rows"] for row in snapshot["sourceValidation"]["sources"]) == snapshot["population"]["rows"],
        "valid_source_rates": all(0 <= row["pricedRows"] <= row["rows"] and 0 <= row["datedRate"] <= 100 and 0 <= row["modelKnownRate"] <= 100 for row in snapshot["sourceValidation"]["sources"]),
    }
    print(json.dumps({"asOf": snapshot["asOf"], "population": snapshot["population"], "checks": checks}, ensure_ascii=False, indent=2))
    for path in [root / "local_dev.db", root.parent / "local_dev.db"]:
        if not path.exists():
            continue
        with sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True) as db:
            tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if "price_platform_comparisons" not in tables:
                print(f"{path.name}: comparison table unavailable")
                continue
            rows = db.execute("SELECT category,platform,sample_count,p25_price,median_price,p75_price FROM price_platform_comparisons").fetchall()
            valid = all(row[2] > 0 and 0 <= row[3] <= row[4] <= row[5] for row in rows)
            print(json.dumps({"database": str(path), "comparisonRows": len(rows), "platforms": sorted({row[1] for row in rows}), "quartilesValid": valid, "uniqueGroups": len({(r[0], r[1]) for r in rows}) == len(rows)}, ensure_ascii=False))
    if not all(checks.values()):
        raise SystemExit("Source validation failed")


if __name__ == "__main__":
    main()
