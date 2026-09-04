"""Viewport queries over Seoul's subway master and live bicycle inventory."""

import json
import math
import threading
import time
from datetime import datetime, timezone
from typing import Literal
from urllib.parse import quote
from urllib.request import urlopen

from fastapi import HTTPException
from pydantic import BaseModel

from app.core.config import settings

TransitKind = Literal['subway', 'bike']


class TransitStop(BaseModel):
    id: str
    kind: TransitKind
    name: str
    lat: float
    lng: float
    line: str | None = None
    bikes_available: int | None = None
    racks: int | None = None


class TransitResponse(BaseModel):
    items: list[TransitStop]
    total: int
    fetched_at: datetime
    source: str = '서울 열린데이터광장'


_cache: dict[str, tuple[float, datetime, list[TransitStop]]] = {}
_locks = {'bike': threading.Lock(), 'subway': threading.Lock()}


def _number(value: object) -> float | None:
    try:
        number = float(str(value).strip())
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def _count(value: object) -> int | None:
    number = _number(value)
    return int(number) if number is not None and number >= 0 and number.is_integer() else None


def _normalize(row: dict, kind: TransitKind) -> TransitStop | None:
    bike = kind == 'bike'
    lat = _number(row.get('stationLatitude' if bike else 'LAT'))
    lng = _number(row.get('stationLongitude' if bike else 'LOT'))
    name = str(row.get('stationName' if bike else 'BLDN_NM') or '').strip()
    identifier = str(row.get('stationId' if bike else 'BLDN_ID') or '').strip()
    if lat is None or lng is None or not 33 <= lat <= 39 or not 124 <= lng <= 132 or not name or not identifier:
        return None
    return TransitStop(
        id=f'{kind}-{identifier}', kind=kind, name=name, lat=lat, lng=lng,
        line=None if bike else str(row.get('ROUTE') or '').strip() or None,
        bikes_available=_count(row.get('parkingBikeTotCnt')) if bike else None,
        racks=_count(row.get('rackTotCnt')) if bike else None,
    )


def _fetch_page(service: str, key: str, start: int, end: int) -> list[dict]:
    base = settings.SEOUL_OPEN_API_BASE_URL.rstrip('/')
    url = f'{base}/{quote(key, safe="")}/json/{service}/{start}/{end}/'
    try:
        with urlopen(url, timeout=8) as response:
            payload = json.load(response)
        envelope = 'rentBikeStatus' if service == 'bikeList' else service
        body = payload.get(envelope, {})
        result = body.get('RESULT') or payload.get('RESULT') or {}
        code = result.get('CODE')
        if code == 'INFO-200':
            return []
        if code != 'INFO-000':
            raise HTTPException(503, '서울시 교통정보를 조회할 수 없어요. 잠시 후 다시 시도해 주세요.')
        rows = body.get('row')
        if not isinstance(rows, list):
            raise ValueError('Unexpected rows')
        return rows
    except HTTPException:
        raise
    except Exception:
        # Provider exceptions can contain the credential-bearing URL.
        raise HTTPException(503, '서울시 교통정보에 연결하지 못했어요. 잠시 후 다시 시도해 주세요.') from None


def _all_stops(kind: TransitKind) -> tuple[datetime, list[TransitStop]]:
    ttl = 60 if kind == 'bike' else 86_400
    with _locks[kind]:
        cached = _cache.get(kind)
        if cached and time.monotonic() - cached[0] < ttl:
            return cached[1], cached[2]
        key = (settings.SEOUL_BIKE_API_KEY if kind == 'bike' else settings.SEOUL_SUBWAY_API_KEY).strip()
        key = key or settings.SEOUL_OPEN_API_KEY.strip() or settings.SEOUL_OPEN_DATA_API_KEY.strip()
        if not key or key == 'sample':
            raise HTTPException(503, '교통정보 연결을 준비 중이에요. 잠시 후 다시 확인해 주세요.')
        service = 'bikeList' if kind == 'bike' else 'subwayStationMaster'
        stops: dict[str, TransitStop] = {}
        # bikeList reports page size, not the full dataset size. Continue until
        # a short/empty page so eastern Seoul is not lost after the first 1000.
        for start in range(1, 20_001, 1000):
            rows = _fetch_page(service, key, start, start + 999)
            for row in rows:
                stop = _normalize(row, kind) if isinstance(row, dict) else None
                if stop:
                    stops[stop.id] = stop
            if len(rows) < 1000:
                break
        else:
            raise HTTPException(503, '교통정보를 모두 불러오지 못했어요. 다시 시도해 주세요.')
        fetched_at = datetime.now(timezone.utc)
        result = list(stops.values())
        _cache[kind] = (time.monotonic(), fetched_at, result)
        return fetched_at, result


def list_transit(kind: TransitKind, south: float, west: float, north: float, east: float, limit: int = 120) -> TransitResponse:
    if not all(math.isfinite(v) for v in (south, west, north, east)) or not (-90 <= south < north <= 90 and -180 <= west < east <= 180):
        raise HTTPException(422, '지도 범위를 확인해 주세요.')
    fetched_at, stops = _all_stops(kind)
    matches = [stop for stop in stops if south <= stop.lat <= north and west <= stop.lng <= east]
    lat, lng = (south + north) / 2, (west + east) / 2
    matches.sort(key=lambda stop: (stop.lat - lat) ** 2 + ((stop.lng - lng) * math.cos(math.radians(lat))) ** 2)
    return TransitResponse(items=matches[:limit], total=len(matches), fetched_at=fetched_at)
