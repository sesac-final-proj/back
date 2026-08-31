#!/usr/bin/env python3
"""서울안전누리 재난·사고 속보 수집기.

화면용 JSON 엔드포인트를 호출하고 원본 응답과 정규화한 사건을 SQLite에
저장한다. 외부 패키지 없이 Python 표준 라이브러리만 사용한다.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import math
import signal
import sqlite3
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener


BASE_URL = "https://safecity.seoul.go.kr"
ENDPOINTS = {
    "disaster": "/news/dist/getDisstList.do",
    "accident": "/news/acdnt/getAcdntList.do",
}

TYPE_KEYWORDS = {
    "단수사고": ("단수", "급수중단", "수도관", "상수도"),
    "호우": ("호우", "폭우", "집중호우", "침수", "강우"),
    "홍수": ("홍수", "하천범람", "범람"),
    "도로돌발": ("도로돌발", "교통사고", "도로통제", "차량고장"),
    "지하철사고": ("지하철", "열차", "전동차"),
    "화재사고": ("화재", "불이", "산불"),
    "태풍": ("태풍",),
    "대설": ("대설", "폭설"),
    "강풍": ("강풍", "돌풍"),
    "지진": ("지진",),
}

ID_KEYS = ("id", "newsId", "newsSn", "seq", "sn", "nttNo", "distId", "acdntId")
TITLE_KEYS = ("title", "ttl", "newsSj", "sj", "subject", "distTitle", "acdntTitle")
CONTENT_KEYS = ("content", "cn", "newsCn", "message", "msg", "cont", "description")
TYPE_KEYS = ("type", "typeNm", "distTy", "distTyNm", "acdntTy", "acdntTyNm", "acdntNm", "pushKey")
DATE_KEYS = ("occurredAt", "occurDate", "regDt", "regDttm", "newsDt", "crtDt", "frstRegistPnttm", "date")
ADDRESS_KEYS = ("address", "addr", "roadAddr", "jibunAddr", "areaNm", "signguNm", "guNm")
LAT_KEYS = ("latitude", "lat", "y", "yloc")
LON_KEYS = ("longitude", "lon", "lng", "x", "xloc")
X_KEYS = ("locX", "xloc")
Y_KEYS = ("locY", "yloc")


@dataclass
class FetchResult:
    source: str
    endpoint: str
    payload: Any
    fetched_at: str


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def first_value(item: dict[str, Any], keys: Iterable[str]) -> Any:
    for key in keys:
        value = item.get(key)
        if value not in (None, ""):
            return value
    return None


def scalar_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (str, int, float, bool)):
        return str(value).strip()
    return ""


def classify(item: dict[str, Any], source: str) -> str:
    supplied = scalar_text(first_value(item, TYPE_KEYS))
    haystack = " ".join(
        scalar_text(v) for v in (
            supplied,
            first_value(item, TITLE_KEYS),
            first_value(item, CONTENT_KEYS),
        )
    ).lower()
    for category, keywords in TYPE_KEYWORDS.items():
        if any(keyword.lower() in haystack for keyword in keywords):
            return category
    if supplied:
        return supplied
    return "기타사고" if source == "accident" else "기타재난"


def looks_like_event(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    keys = set(value)
    signal_keys = set(ID_KEYS + TITLE_KEYS + CONTENT_KEYS + TYPE_KEYS + DATE_KEYS)
    return bool(keys & signal_keys) and not all(isinstance(v, (dict, list)) for v in value.values())


def iter_events(value: Any) -> Iterable[dict[str, Any]]:
    """응답 래퍼 이름이 바뀌어도 사건 객체를 재귀적으로 찾는다."""
    if isinstance(value, list):
        for child in value:
            yield from iter_events(child)
    elif isinstance(value, dict):
        if looks_like_event(value):
            yield value
            return
        for child in value.values():
            if isinstance(child, (list, dict)):
                yield from iter_events(child)


def epsg5186_to_wgs84(x: float, y: float) -> tuple[float, float]:
    """EPSG:5186 (서울시 TM 평면좌표) -> EPSG:4326 (네이버지도 WGS84 위도, 경도) 변환"""
    a = 6378137.0
    f = 1.0 / 298.257222101
    b = a * (1.0 - f)
    e2 = (a**2 - b**2) / (a**2)
    e_prime2 = (a**2 - b**2) / (b**2)
    
    lat0 = math.radians(38.0)
    lon0 = math.radians(127.0)
    k0 = 1.0
    fe = 200000.0
    fn = 500000.0
    
    x_val = x - fe
    y_val = y - fn
    
    n = (a - b) / (a + b)
    alpha = (a + b) / 2.0 * (1.0 + n**2 / 4.0 + n**4 / 64.0)
    
    y_prime = y_val / k0
    M0 = alpha * lat0 - (a + b)/2.0 * (
        (3.0/2.0*n - 9.0/16.0*n**3) * math.sin(2*lat0)
        + (15.0/16.0*n**2 - 15.0/32.0*n**4) * math.sin(4*lat0)
        + (35.0/48.0*n**3) * math.sin(6*lat0)
    )
    M = M0 + y_prime
    
    mu = M / alpha
    e1 = (1.0 - math.sqrt(1.0 - e2)) / (1.0 + math.sqrt(1.0 - e2))
    
    lat1 = mu + (3.0/2.0*e1 - 27.0/32.0*e1**3) * math.sin(2*mu) + (21.0/16.0*e1**2 - 55.0/32.0*e1**4) * math.sin(4*mu) + (151.0/96.0*e1**3) * math.sin(6*mu) + (1097.0/512.0*e1**4) * math.sin(8*mu)
    
    N1 = a / math.sqrt(1.0 - e2 * math.sin(lat1)**2)
    T1 = math.tan(lat1)**2
    C1 = e_prime2 * math.cos(lat1)**2
    R1 = a * (1.0 - e2) / ((1.0 - e2 * math.sin(lat1)**2)**1.5)
    D = x_val / (N1 * k0)
    
    lat = lat1 - (N1 * math.tan(lat1) / R1) * (
        D**2 / 2.0
        - (5.0 + 3.0*T1 + 10.0*C1 - 4.0*C1**2 - 9.0*e_prime2) * D**4 / 24.0
        + (61.0 + 90.0*T1 + 298.0*C1 + 45.0*T1**2 - 252.0*e_prime2 - 3.0*C1**2) * D**6 / 720.0
    )
    
    lon = lon0 + (
        D
        - (1.0 + 2.0*T1 + C1) * D**3 / 6.0
        + (5.0 - 2.0*C1 + 28.0*T1 - 3.0*C1**2 + 8.0*e_prime2 + 24.0*T1**2) * D**5 / 120.0
    ) / math.cos(lat1)
    
    return round(math.degrees(lat), 7), round(math.degrees(lon), 7)


def make_event(source: str, item: dict[str, Any], collected_at: str) -> dict[str, Any]:
    title = scalar_text(first_value(item, TITLE_KEYS))
    content = scalar_text(first_value(item, CONTENT_KEYS))
    occurred_at = scalar_text(first_value(item, DATE_KEYS))
    supplied_id = scalar_text(first_value(item, ID_KEYS))
    # title, content, occurred_at가 존재하는 경우 이를 기반으로 해시 고유 ID를 생성하여 동일 사건 중복을 완전 제거
    if title or content or occurred_at:
        identity = "|".join((source, title, content, occurred_at))
    else:
        identity = supplied_id or "|".join((source, title, content, occurred_at))
    event_id = hashlib.sha256(identity.encode("utf-8")).hexdigest()

    lat_str = scalar_text(first_value(item, LAT_KEYS))
    lon_str = scalar_text(first_value(item, LON_KEYS))
    coord_x_str = scalar_text(first_value(item, X_KEYS))
    coord_y_str = scalar_text(first_value(item, Y_KEYS))

    # 네이버지도(WGS84 EPSG:4326 위도/경도) 자동 변환 처리
    if (not lat_str or not lon_str) and (coord_x_str and coord_y_str):
        try:
            cx = float(coord_x_str)
            cy = float(coord_y_str)
            wgs_lat, wgs_lon = epsg5186_to_wgs84(cx, cy)
            lat_str = str(wgs_lat)
            lon_str = str(wgs_lon)
        except (ValueError, TypeError):
            pass

    return {
        "event_id": event_id,
        "source_id": supplied_id,
        "source": source,
        "category": classify(item, source),
        "title": title,
        "content": content,
        "occurred_at": occurred_at,
        "address": scalar_text(first_value(item, ADDRESS_KEYS)),
        "latitude": lat_str,
        "longitude": lon_str,
        "coord_x": coord_x_str,
        "coord_y": coord_y_str,
        "coord_crs": "EPSG:4326 (WGS84) / EPSG:5186" if (coord_x_str and coord_y_str) else "",
        "source_url": BASE_URL + ENDPOINTS[source],
        "collected_at": collected_at,
        "raw_json": json.dumps(item, ensure_ascii=False, separators=(",", ":")),
    }


class SafeCityClient:
    def __init__(self, timeout: float = 20.0) -> None:
        self.timeout = timeout
        self.opener = build_opener(HTTPCookieProcessor(CookieJar()))
        self.headers = {
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "User-Agent": "Mozilla/5.0 (compatible; SeoulSafeCityCollector/1.0)",
            "Referer": BASE_URL + "/",
            "X-Requested-With": "XMLHttpRequest",
        }

    def start_session(self) -> None:
        request = Request(BASE_URL + "/", headers={"User-Agent": self.headers["User-Agent"]})
        with self.opener.open(request, timeout=self.timeout):
            pass

    def fetch(self, source: str) -> FetchResult:
        endpoint = ENDPOINTS[source]
        data = urlencode({}).encode("ascii")
        request = Request(BASE_URL + endpoint, data=data, headers=self.headers, method="POST")
        with self.opener.open(request, timeout=self.timeout) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            text = response.read().decode(charset, errors="replace")
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            preview = text[:200].replace("\n", " ")
            raise RuntimeError(f"{source} 응답이 JSON이 아닙니다: {preview}") from exc
        return FetchResult(source, endpoint, payload, now_iso())


def connect_db(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS fetch_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            endpoint TEXT NOT NULL,
            fetched_at TEXT NOT NULL,
            item_count INTEGER NOT NULL,
            raw_json TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS events (
            event_id TEXT PRIMARY KEY,
            source_id TEXT,
            source TEXT NOT NULL,
            category TEXT NOT NULL,
            title TEXT,
            content TEXT,
            occurred_at TEXT,
            address TEXT,
            latitude TEXT,
            longitude TEXT,
            coord_x TEXT,
            coord_y TEXT,
            coord_crs TEXT,
            source_url TEXT NOT NULL,
            first_collected_at TEXT NOT NULL,
            last_collected_at TEXT NOT NULL,
            raw_json TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_events_category ON events(category);
        CREATE INDEX IF NOT EXISTS idx_events_occurred_at ON events(occurred_at);
        """
    )
    # 기존 DB도 새 지도 좌표 필드를 사용할 수 있도록 가볍게 마이그레이션한다.
    columns = {row[1] for row in connection.execute("PRAGMA table_info(events)")}
    for name in ("coord_x", "coord_y", "coord_crs"):
        if name not in columns:
            connection.execute(f"ALTER TABLE events ADD COLUMN {name} TEXT")
    connection.commit()
    return connection


def save_result(connection: sqlite3.Connection, result: FetchResult) -> tuple[int, int]:
    events = [make_event(result.source, item, result.fetched_at) for item in iter_events(result.payload)]
    new_count = 0
    for event in events:
        before = connection.total_changes
        connection.execute(
            """
            INSERT INTO events (
                event_id, source_id, source, category, title, content, occurred_at,
                address, latitude, longitude, coord_x, coord_y, coord_crs,
                source_url, first_collected_at,
                last_collected_at, raw_json
            ) VALUES (
                :event_id, :source_id, :source, :category, :title, :content, :occurred_at,
                :address, :latitude, :longitude, :coord_x, :coord_y, :coord_crs,
                :source_url, :collected_at,
                :collected_at, :raw_json
            )
            ON CONFLICT(event_id) DO UPDATE SET
                category=excluded.category, title=excluded.title, content=excluded.content,
                occurred_at=excluded.occurred_at, address=excluded.address,
                latitude=excluded.latitude, longitude=excluded.longitude,
                coord_x=excluded.coord_x, coord_y=excluded.coord_y,
                coord_crs=excluded.coord_crs,
                last_collected_at=excluded.last_collected_at, raw_json=excluded.raw_json
            """,
            event,
        )
        if connection.total_changes > before:
            exists = connection.execute(
                "SELECT first_collected_at = last_collected_at FROM events WHERE event_id=?",
                (event["event_id"],),
            ).fetchone()[0]
            new_count += int(exists)
    connection.execute(
        "INSERT INTO fetch_log(source, endpoint, fetched_at, item_count, raw_json) VALUES (?, ?, ?, ?, ?)",
        (
            result.source,
            result.endpoint,
            result.fetched_at,
            len(events),
            json.dumps(result.payload, ensure_ascii=False, separators=(",", ":")),
        ),
    )
    connection.commit()
    return len(events), new_count


def collect_once(client: SafeCityClient, connection: sqlite3.Connection) -> bool:
    success = False
    for source in ENDPOINTS:
        try:
            result = client.fetch(source)
            total, new = save_result(connection, result)
            logging.info("%s: %d건 확인, 신규 %d건", source, total, new)
            success = True
        except (HTTPError, URLError, TimeoutError, RuntimeError) as exc:
            logging.error("%s 수집 실패: %s", source, exc)
    return success


def export_json(connection: sqlite3.Connection, path: Path) -> int:
    """현재 사건 전체를 읽기 쉬운 JSON 파일로 원자적으로 내보낸다."""
    connection.row_factory = sqlite3.Row
    rows = connection.execute(
        """
        SELECT event_id, source_id, source, category, title, content,
               occurred_at, address, latitude, longitude,
               coord_x, coord_y, coord_crs, source_url,
               first_collected_at, last_collected_at, raw_json
        FROM events
        ORDER BY occurred_at DESC, last_collected_at DESC
        """
    ).fetchall()
    events = []
    for row in rows:
        event = dict(row)
        raw = event.pop("raw_json", "")
        try:
            event["raw_data"] = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            event["raw_data"] = raw
        events.append(event)

    document = {
        "source": "서울안전누리",
        "source_url": BASE_URL + "/",
        "exported_at": now_iso(),
        "count": len(events),
        "events": events,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)
    return len(events)


DISTRICT_MATCHING = {
    "영등포구": {
        "keywords": ["영등포", "여의도", "문래", "당산", "양평", "신길", "대림", "양화", "경인로"],
        "lat_min": 37.48, "lat_max": 37.56,
        "lon_min": 126.87, "lon_max": 126.96,
    },
    "노원구": {
        "keywords": ["노원", "상계", "중계", "하계", "월계", "공릉", "마들로", "동일로"],
        "lat_min": 37.60, "lat_max": 37.71,
        "lon_min": 127.04, "lon_max": 127.12,
    },
    "송파구": {
        "keywords": ["송파", "잠실", "가락", "문정", "방이", "오금", "석촌", "신천", "풍납", "장지", "삼전", "마천", "거여", "올림픽로", "양재대로"],
        "lat_min": 37.46, "lat_max": 37.55,
        "lon_min": 127.07, "lon_max": 127.17,
    },
}


def event_matches_region(event: dict, region: str) -> bool:
    if not region:
        return True
    reg = region.strip()
    if not reg:
        return True
        
    reg_clean = reg.rstrip("구").lower()
    haystack = " ".join(
        str(event.get(k) or "") for k in ("address", "title", "content")
    ).lower()
    
    # 1. Direct string match (e.g. "영등포구" or "영등포")
    if reg.lower() in haystack or (reg_clean and reg_clean in haystack):
        return True

    # 2. Known district keyword or coordinate bounding box match
    dist_info = DISTRICT_MATCHING.get(reg) or DISTRICT_MATCHING.get(reg + "구")
    if dist_info:
        for kw in dist_info.get("keywords", []):
            if kw.lower() in haystack:
                return True
        lat_str = event.get("latitude")
        lon_str = event.get("longitude")
        if lat_str and lon_str:
            try:
                lat = float(lat_str)
                lon = float(lon_str)
                if dist_info["lat_min"] <= lat <= dist_info["lat_max"] and dist_info["lon_min"] <= lon <= dist_info["lon_max"]:
                    return True
            except (ValueError, TypeError):
                pass

    return False


def export_csv(connection: sqlite3.Connection, path: Path, region: str = "") -> int:
    """현재 수집된 사건들을 CSV 파일(UTF-8-BOM 인코딩)로 원자적으로 저장한다."""
    connection.row_factory = sqlite3.Row
    query = """
        SELECT event_id, source_id, source, category, title, content,
               occurred_at, address, latitude, longitude,
               coord_x, coord_y, coord_crs, source_url,
               first_collected_at, last_collected_at
        FROM events
        ORDER BY occurred_at DESC, last_collected_at DESC
    """
    rows = connection.execute(query).fetchall()
    
    fieldnames = [
        "event_id", "source_id", "source", "category", "title", "content",
        "occurred_at", "address", "latitude", "longitude",
        "coord_x", "coord_y", "coord_crs", "source_url",
        "first_collected_at", "last_collected_at"
    ]
    
    seen_signatures = set()
    filtered_events = []

    for row in rows:
        event = dict(row)
        
        # 중복 제거: 제목, 내용, 발생시각이 동일한 사건은 1건만 유지
        sig = (event.get("title") or "", event.get("content") or "", event.get("occurred_at") or "")
        if sig in seen_signatures:
            continue
        seen_signatures.add(sig)

        # 네이버지도용 WGS84 위도(latitude), 경도(longitude) 자동 계산 및 채우기
        cx_val = event.get("coord_x")
        cy_val = event.get("coord_y")
        if (not event.get("latitude") or not event.get("longitude")) and (cx_val and cy_val):
            try:
                wgs_lat, wgs_lon = epsg5186_to_wgs84(float(cx_val), float(cy_val))
                event["latitude"] = str(wgs_lat)
                event["longitude"] = str(wgs_lon)
                event["coord_crs"] = "EPSG:4326 (WGS84)"
            except (ValueError, TypeError):
                pass

        if region and not event_matches_region(event, region):
            continue

        filtered_events.append(event)
        
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(filtered_events)
    temporary.replace(path)
    return len(filtered_events)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="서울안전누리 사고·재난 속보 수집기")
    parser.add_argument("--db", type=Path, default=Path("safecity.sqlite3"), help="SQLite 파일")
    parser.add_argument(
        "--json",
        type=Path,
        default=Path("safecity_events.json"),
        help="매 수집 후 생성할 JSON 파일",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=Path("safecity_events.csv"),
        help="매 수집 후 생성할 전체 CSV 파일",
    )
    parser.add_argument("--region", type=str, default="", help="단일 지역 필터 (예: '은평구')")
    parser.add_argument(
        "--districts",
        type=str,
        default="영등포구,송파구,노원구",
        help="구별 CSV 파일로 자동 저장할 구 목록 (쉼표 구분, 기본값: '영등포구,송파구,노원구')",
    )
    parser.add_argument("--interval", type=int, default=600, help="반복 주기(초, 기본값: 600초 = 10분)")
    parser.add_argument("--once", action="store_true", help="한 번만 수집하고 종료")
    parser.add_argument("--timeout", type=float, default=20.0, help="HTTP 제한 시간(초)")
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    connection = connect_db(args.db)
    client = SafeCityClient(args.timeout)
    try:
        client.start_session()
    except (HTTPError, URLError, TimeoutError) as exc:
        logging.error("서울안전누리 접속 실패: %s", exc)
        return 1

    stopping = False

    def stop(_signum: int, _frame: Any) -> None:
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGINT, stop)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, stop)

    try:
        while not stopping:
            ok = collect_once(client, connection)
            if ok:
                if args.json:
                    json_count = export_json(connection, args.json)
                    logging.info("JSON 저장: %s (%d건)", args.json, json_count)
                if args.csv:
                    csv_count = export_csv(connection, args.csv, region=args.region)
                    region_info = f" [지역 필터: {args.region}]" if args.region else ""
                    logging.info("전체 CSV 저장: %s (%d건%s)", args.csv, csv_count, region_info)
                
                # 구별 CSV 파일 저장 (영등포구, 송파구, 노원구 등)
                if args.districts:
                    target_districts = [d.strip() for d in args.districts.split(",") if d.strip()]
                    csv_dir = args.csv.parent if args.csv else Path(__file__).parent
                    for dist in target_districts:
                        dist_csv_path = csv_dir / f"safecity_{dist}.csv"
                        dist_count = export_csv(connection, dist_csv_path, region=dist)
                        logging.info("구별 CSV 저장: %s (%d건)", dist_csv_path.name, dist_count)

            if args.once:
                return 0 if ok else 1
            deadline = time.monotonic() + max(10, args.interval)
            while not stopping and time.monotonic() < deadline:
                time.sleep(min(1.0, deadline - time.monotonic()))
    finally:
        connection.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
