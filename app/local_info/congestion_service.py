import json
import logging
import math
import os
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


class CongestionUnavailableError(Exception):
    pass

# 핫스팟 메타데이터 파일 경로
HOTSPOTS_FILE = Path(__file__).parent / "seoul_hotspots.json"

# 인메모리 실시간 도시데이터 캐시 { poi_code: { 'data': dict, 'expires_at': float } }
_CITYDATA_CACHE: Dict[str, Dict[str, Any]] = {}
CACHE_TTL_SECONDS = 300  # 5분 캐시


def load_hotspots() -> List[Dict[str, Any]]:
    if not HOTSPOTS_FILE.exists():
        logger.warning("seoul_hotspots.json not found at %s", HOTSPOTS_FILE)
        return []
    try:
        with open(HOTSPOTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error("Failed to load hotspots: %s", e)
        return []


def get_citydata_api_key() -> str:
    key = settings.SEOUL_CITYDATA_SERVICE or settings.SEOUL_OPEN_API_KEY or settings.SEOUL_OPEN_DATA_API_KEY
    return key.strip() if key else ""


def fetch_citydata_ppltn_raw(poi_code: str) -> Optional[Dict[str, Any]]:
    """서울시 실시간 도시데이터(인구/혼잡도) API 단건 호출 (TTL 캐시 적용)"""
    now = time.time()
    cached = _CITYDATA_CACHE.get(poi_code)
    if cached and cached["expires_at"] > now:
        return cached["data"]

    key = get_citydata_api_key()
    if not key:
        return None

    base_url = (settings.SEOUL_OPEN_API_BASE_URL or "http://openapi.seoul.go.kr:8088").rstrip("/")
    url = f"{base_url}/{key}/json/citydata_ppltn/1/1/{urllib.parse.quote(poi_code)}"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "GajiMarket-Server/1.0"})
        with urllib.request.urlopen(req, timeout=3.5) as response:
            payload = json.loads(response.read().decode("utf-8"))
            if "SeoulRtd.citydata_ppltn" in payload:
                items = payload["SeoulRtd.citydata_ppltn"]
                if items and isinstance(items, list):
                    res_data = items[0]
                    _CITYDATA_CACHE[poi_code] = {
                        "data": res_data,
                        "expires_at": now + CACHE_TTL_SECONDS,
                    }
                    return res_data
    except Exception as e:
        logger.warning("Citydata request failed for %s (%s)", poi_code, type(e).__name__)

    return None


def parse_congestion_score(level_str: str) -> tuple[int, str]:
    """Rendering weights for API categories, not measured percentages."""
    levels = {"여유": (22, "low"), "보통": (60, "moderate"), "약간 붐빔": (78, "high"), "붐빔": (92, "severe"), "매우 붐빔": (92, "severe")}
    return levels.get((level_str or "").strip(), (0, "unknown"))


def _population(value: Any) -> Optional[int]:
    try:
        return max(0, int(str(value).replace(",", "")))
    except (ValueError, TypeError):
        return None


def get_congestion_zones(
    sw_lat: Optional[float] = None, sw_lng: Optional[float] = None,
    ne_lat: Optional[float] = None, ne_lng: Optional[float] = None,
    neighborhood: Optional[str] = None, limit: int = 40,
) -> List[Dict[str, Any]]:
    hotspots = load_hotspots()
    bounds = (sw_lat, sw_lng, ne_lat, ne_lng)
    if any(value is not None for value in bounds):
        if not all(value is not None and math.isfinite(value) for value in bounds):
            raise ValueError("All four finite coordinates are required")
        if not (-90 <= sw_lat < ne_lat <= 90 and -180 <= sw_lng < ne_lng <= 180):
            raise ValueError("Invalid map bounds")
        matched = [spot for spot in hotspots if sw_lat <= spot["lat"] <= ne_lat and sw_lng <= spot["lng"] <= ne_lng]
        center_lat, center_lng = (sw_lat + ne_lat) / 2, (sw_lng + ne_lng) / 2
        matched.sort(key=lambda spot: math.hypot(spot["lat"] - center_lat, (spot["lng"] - center_lng) * math.cos(math.radians(center_lat))))
    elif neighborhood and neighborhood.strip():
        matched = [spot for spot in hotspots if neighborhood in spot.get("neighborhood", "") or neighborhood in spot["name"]]
    else:
        return []
    matched = matched[:max(1, min(limit, 100))]
    if not matched:
        return []
    if not get_citydata_api_key():
        raise CongestionUnavailableError("Seoul API key is not configured")

    def fetch_zone(spot: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        realtime = fetch_citydata_ppltn_raw(spot["poi"])
        if not realtime:
            return None
        # Never attach a different area's reading to a catalogue coordinate.
        if realtime.get("AREA_CD") and realtime["AREA_CD"] != spot["poi"]:
            return None
        label = realtime.get("AREA_CONGEST_LVL", "").strip()
        score, level = parse_congestion_score(label)
        if level == "unknown":
            return None
        return {
            "id": f"seoul-{spot['poi']}", "name": realtime.get("AREA_NM") or spot["name"],
            "neighborhoodName": spot.get("neighborhood", ""), "districtName": spot.get("district", "서울"),
            "lat": spot["lat"], "lng": spot["lng"], "distance": "",
            "currentScore": score, "level": level, "levelLabel": label,
            "populationMin": _population(realtime.get("AREA_PPLTN_MIN")),
            "populationMax": _population(realtime.get("AREA_PPLTN_MAX")),
            "summary": realtime.get("AREA_CONGEST_MSG") or "",
            "updatedAt": realtime.get("PPLTN_TIME") or "갱신 시간 미제공",
            "source": "seoul_citydata_api",
        }

    with ThreadPoolExecutor(max_workers=6) as executor:
        zones = [zone for zone in executor.map(fetch_zone, matched) if zone is not None]
    if not zones:
        raise CongestionUnavailableError("No live readings are available for this area")
    return zones
