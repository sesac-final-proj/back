#!/usr/bin/env python3
"""서울안전누리 CSV를 백엔드의 Supabase PostgreSQL에 업서트한다."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


NURI_DIR = Path(__file__).resolve().parent
BACKEND_ROOT = NURI_DIR.parent
KST = timezone(timedelta(hours=9))
SOURCE = "seoul_safecity"


def empty_to_none(value: str | None) -> str | None:
    text = (value or "").strip()
    return text or None


def parse_datetime(value: str | None) -> datetime | None:
    text = empty_to_none(value)
    if text is None:
        return None
    parsed = datetime.fromisoformat(text)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=KST)


def parse_float(value: str | None) -> float | None:
    text = empty_to_none(value)
    if text is None:
        return None
    return float(text)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def district_memberships(csv_dir: Path) -> dict[str, list[str]]:
    memberships: dict[str, list[str]] = {}
    for path in sorted(csv_dir.glob("safecity_*.csv")):
        if path.name == "safecity_events.csv":
            continue
        district = path.stem.removeprefix("safecity_")
        for row in read_csv(path):
            event_id = empty_to_none(row.get("event_id"))
            if event_id:
                memberships.setdefault(event_id, []).append(district)
    return memberships


def build_records(csv_path: Path) -> list[dict[str, Any]]:
    rows = read_csv(csv_path)
    memberships = district_memberships(csv_path.parent)
    records: list[dict[str, Any]] = []

    for line_number, row in enumerate(rows, start=2):
        event_id = empty_to_none(row.get("event_id"))
        category = empty_to_none(row.get("category"))
        if not event_id or not category:
            raise ValueError(f"{csv_path.name}:{line_number} event_id/category가 비어 있습니다")

        matched_districts = sorted(set(memberships.get(event_id, [])))
        raw_data: dict[str, Any] = dict(row)
        raw_data["matched_districts"] = matched_districts

        records.append(
            {
                "source": SOURCE,
                "external_id": event_id,
                "risk_type": category,
                "risk_name": empty_to_none(row.get("title")),
                "address": empty_to_none(row.get("address")),
                "sido": "서울특별시",
                "sigungu": matched_districts[0] if len(matched_districts) == 1 else None,
                "latitude": parse_float(row.get("latitude")),
                "longitude": parse_float(row.get("longitude")),
                "description": empty_to_none(row.get("content")),
                "observed_at": parse_datetime(row.get("occurred_at")),
                "crawled_at": parse_datetime(row.get("last_collected_at")) or datetime.now(KST),
                "source_url": empty_to_none(row.get("source_url")),
                "raw_data": json.dumps(raw_data, ensure_ascii=False, separators=(",", ":")),
            }
        )
    return records


def upload(records: list[dict[str, Any]]) -> tuple[int, int]:
    sys.path.insert(0, str(BACKEND_ROOT))
    from dotenv import load_dotenv
    from sqlalchemy import text

    load_dotenv(BACKEND_ROOT / ".env")
    from app.core.db import engine

    statement = text(
        """
        insert into public.nuri_crawled (
            source, external_id, risk_type, risk_name, address, sido, sigungu,
            latitude, longitude, description, observed_at, crawled_at,
            source_url, raw_data
        ) values (
            :source, :external_id, :risk_type, :risk_name, :address, :sido, :sigungu,
            :latitude, :longitude, :description, :observed_at, :crawled_at,
            :source_url, cast(:raw_data as jsonb)
        )
        on conflict (source, external_id) do update set
            risk_type = excluded.risk_type,
            risk_name = excluded.risk_name,
            address = excluded.address,
            sido = excluded.sido,
            sigungu = excluded.sigungu,
            latitude = excluded.latitude,
            longitude = excluded.longitude,
            description = excluded.description,
            observed_at = excluded.observed_at,
            crawled_at = excluded.crawled_at,
            source_url = excluded.source_url,
            raw_data = excluded.raw_data
        """
    )
    count_statement = text(
        "select count(*) from public.nuri_crawled where source = :source"
    )

    with engine.begin() as connection:
        before = int(connection.execute(count_statement, {"source": SOURCE}).scalar_one())
        connection.execute(statement, records)
        after = int(connection.execute(count_statement, {"source": SOURCE}).scalar_one())
    return after - before, after


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="서울안전누리 CSV Supabase 업로더")
    parser.add_argument(
        "--csv",
        type=Path,
        default=NURI_DIR / "safecity_events.csv",
        help="전체 사건 CSV 경로",
    )
    parser.add_argument("--dry-run", action="store_true", help="DB에 쓰지 않고 변환만 검증")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    records = build_records(args.csv.resolve())
    if args.dry_run:
        tagged = sum(record["sigungu"] is not None for record in records)
        print(f"변환 검증 완료: {len(records)}건, 단일 구 매핑 {tagged}건")
        return 0

    inserted, total = upload(records)
    print(f"Supabase 업서트 완료: 처리 {len(records)}건, 신규 {inserted}건, 누적 {total}건")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
