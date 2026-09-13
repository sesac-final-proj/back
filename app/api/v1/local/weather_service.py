import json
import math
import time
from datetime import datetime, timedelta
from urllib.parse import unquote, urlencode
from urllib.request import urlopen
from zoneinfo import ZoneInfo

from app.core.config import settings

BASE_URL = "https://apihub.kma.go.kr/api/typ02/openApi/VilageFcstInfoService_2.0"
MAP_URL = "https://apihub.kma.go.kr/api/typ03/cgi/dfs/nph-dfs_vsrt_ana2"
AIR_URL = "https://apis.data.go.kr/B552584/ArpltnInforInqireSvc/getCtprvnRltmMesureDnsty"
KST = ZoneInfo("Asia/Seoul")
_air_cache: tuple[float, dict | None] | None = None


def _grid(lat: float, lng: float) -> tuple[int, int]:
    re = 6371.00877 / 5.0
    slat1, slat2, olon, olat = map(math.radians, (30.0, 60.0, 126.0, 38.0))
    sn = math.log(math.cos(slat1) / math.cos(slat2)) / math.log(math.tan(math.pi / 4 + slat2 / 2) / math.tan(math.pi / 4 + slat1 / 2))
    sf = math.tan(math.pi / 4 + slat1 / 2) ** sn * math.cos(slat1) / sn
    ro = re * sf / math.tan(math.pi / 4 + olat / 2) ** sn
    ra = re * sf / math.tan(math.pi / 4 + math.radians(lat) / 2) ** sn
    theta = (math.radians(lng) - olon) * sn
    return int(ra * math.sin(theta) + 43.5), int(ro - ra * math.cos(theta) + 136.5)


def _short_base(now: datetime) -> datetime:
    ready = now - timedelta(minutes=10)
    slots = [hour for hour in (2, 5, 8, 11, 14, 17, 20, 23) if hour <= ready.hour]
    return ready.replace(hour=slots[-1], minute=0, second=0, microsecond=0) if slots else (ready - timedelta(days=1)).replace(hour=23, minute=0, second=0, microsecond=0)


def _request(path: str, base: datetime, nx: int, ny: int) -> list[dict]:
    query = urlencode({"pageNo": 1, "numOfRows": 1000, "dataType": "JSON", "base_date": base.strftime("%Y%m%d"), "base_time": base.strftime("%H%M"), "nx": nx, "ny": ny, "authKey": settings.WEATHER_API_KEY})
    with urlopen(f"{BASE_URL}/{path}?{query}", timeout=8) as response:
        payload = json.load(response)
    header = payload["response"]["header"]
    if str(header["resultCode"]) != "00":
        raise RuntimeError(header.get("resultMsg", "weather API error"))
    return payload["response"]["body"]["items"]["item"]


def _rows(items: list[dict], temperature_key: str) -> list[dict]:
    grouped: dict[str, dict] = {}
    for item in items:
        key = f'{item["fcstDate"]}{item["fcstTime"]}'
        grouped.setdefault(key, {"dateTime": key})[item["category"]] = item["fcstValue"]
    result = []
    for row in sorted(grouped.values(), key=lambda value: value["dateTime"]):
        if temperature_key not in row:
            continue
        pty, sky = int(row.get("PTY", 0)), int(row.get("SKY", 1))
        condition = "비" if pty in (1, 2, 5, 6) else "눈" if pty in (3, 7) else "흐림" if sky >= 4 else "구름많음" if sky == 3 else "맑음"
        result.append({"dateTime": row["dateTime"], "temperature": float(row[temperature_key]), "condition": condition, "iconUrl": "", "precipitationProbability": int(row.get("POP", 100 if pty else 0)), "humidity": int(row.get("REH", 0)), "windSpeed": float(row.get("WSD", 0))})
    return result


def _air_quality() -> dict | None:
    global _air_cache
    if not settings.AIR_KOREA_SERVICE_KEY:
        return None
    now = time.monotonic()
    if _air_cache and _air_cache[0] > now:
        return _air_cache[1]
    query = urlencode({
        "serviceKey": unquote(settings.AIR_KOREA_SERVICE_KEY),
        "returnType": "json",
        "numOfRows": 100,
        "pageNo": 1,
        "sidoName": "서울",
    })
    with urlopen(f"{AIR_URL}?{query}", timeout=8) as response:
        rows = json.load(response).get("response", {}).get("body", {}).get("items", [])
    pm10 = [float(row["pm10Value"]) for row in rows if str(row.get("pm10Value", "")).isdigit()]
    pm25 = [float(row["pm25Value"]) for row in rows if str(row.get("pm25Value", "")).isdigit()]
    if not pm10 or not pm25:
        raise RuntimeError("air quality is empty")
    average_pm10 = round(sum(pm10) / len(pm10))
    average_pm25 = round(sum(pm25) / len(pm25))
    grade = "좋음" if average_pm10 <= 30 and average_pm25 <= 15 else "보통" if average_pm10 <= 80 and average_pm25 <= 35 else "나쁨" if average_pm10 <= 150 and average_pm25 <= 75 else "매우 나쁨"
    result = {"pm10": average_pm10, "pm25": average_pm25, "grade": grade, "scope": "서울 평균"}
    _air_cache = (now + 600, result)
    return result


def get_weather(lat: float, lng: float) -> dict:
    if not settings.WEATHER_API_KEY:
        raise RuntimeError("WEATHER_API_KEY is not configured")
    now = datetime.now(KST)
    nx, ny = _grid(lat, lng)
    ultra_base = (now - timedelta(minutes=40)).replace(minute=((now - timedelta(minutes=40)).minute // 10) * 10, second=0, microsecond=0)
    ultra = _rows(_request("getUltraSrtFcst", ultra_base, nx, ny), "T1H")
    short_base = _short_base(now)
    short = _rows(_request("getVilageFcst", short_base, nx, ny), "TMP")
    current_key = now.strftime("%Y%m%d%H00")
    ultra_times = {item["dateTime"] for item in ultra}
    all_items = ultra + [item for item in short if item["dateTime"] not in ultra_times]
    future_items = [item for item in all_items if item["dateTime"] >= current_key]
    forecast = sorted(future_items or all_items, key=lambda item: item["dateTime"])[:18]
    if not forecast:
        raise RuntimeError("weather forecast is empty")
    try:
        air_quality = _air_quality()
    except (OSError, ValueError, KeyError, json.JSONDecodeError):
        air_quality = None
    return {"updatedAt": ultra_base.isoformat(), "current": forecast[0], "forecast": forecast, "airQuality": air_quality}


def get_weather_distribution() -> bytes:
    now = datetime.now(KST)
    base = (now - timedelta(minutes=40)).replace(minute=((now - timedelta(minutes=40)).minute // 10) * 10, second=0, microsecond=0)
    target = (base + timedelta(hours=1)).replace(minute=0)
    query = urlencode({"data0": "GEMD", "tm_fc": base.strftime("%Y%m%d%H%M"), "data1": "T1H", "tm_ef": target.strftime("%Y%m%d%H%M"), "dtm": "H0", "map": "G1", "mask": "M", "color": "E", "size": 700, "effect": "GTL", "overlay": "S", "zoom_rate": 2, "zoom_level": 0, "zoom_x": "0000000", "zoom_y": "0000000", "auto_man": "m", "mode": "I", "authKey": settings.WEATHER_API_KEY})
    with urlopen(f"{MAP_URL}?{query}", timeout=12) as response:
        content = response.read()
    if not content.startswith((b"\x89PNG", b"\xff\xd8\xff", b"GIF")):
        raise RuntimeError("weather distribution image is unavailable")
    return content
