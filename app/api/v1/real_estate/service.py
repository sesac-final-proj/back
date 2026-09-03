import hashlib
import json
import threading
import time
from urllib.error import URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from fastapi import HTTPException, status

from app.api.v1.real_estate import schema
from app.core.config import settings

SEOUL_RENT_API = "http://openapi.seoul.go.kr:8088"
NAVER_GEOCODE_API = "https://maps.apigw.ntruss.com/map-geocode/v2/geocode"
GEOCODE_TTL_SECONDS = 60 * 60 * 24
MAX_GEOCODES_PER_REQUEST = 60

DISTRICT_CODES = {
    "종로구": "11110",
    "중구": "11140",
    "용산구": "11170",
    "성동구": "11200",
    "광진구": "11215",
    "동대문구": "11230",
    "중랑구": "11260",
    "성북구": "11290",
    "강북구": "11305",
    "도봉구": "11320",
    "노원구": "11350",
    "은평구": "11380",
    "서대문구": "11410",
    "마포구": "11440",
    "양천구": "11470",
    "강서구": "11500",
    "구로구": "11530",
    "금천구": "11545",
    "영등포구": "11560",
    "동작구": "11590",
    "관악구": "11620",
    "서초구": "11650",
    "강남구": "11680",
    "송파구": "11710",
    "강동구": "11740",
}

_geocode_cache: dict[str, tuple[float, tuple[float, float] | None]] = {}
_geocode_lock = threading.Lock()


def _fetch_json(url: str, headers: dict[str, str] | None = None) -> dict:
    request = Request(url, headers=headers or {}, method="GET")
    try:
        with urlopen(request, timeout=12) as response:
            return json.loads(response.read().decode("utf-8"))
    except (OSError, URLError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="부동산 실거래 정보를 불러오지 못했습니다.",
        ) from exc


def _to_int(value: object) -> int:
    try:
        return int(float(str(value or "0").replace(",", "")))
    except ValueError:
        return 0


def _to_float(value: object) -> float:
    try:
        return float(str(value or "0").replace(",", ""))
    except ValueError:
        return 0.0


def _clean_lot_number(value: object) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    return str(int(raw)) if raw.isdigit() else raw


def _address(row: dict) -> str:
    district = str(row.get("CGG_NM") or "").strip()
    dong = str(row.get("STDG_NM") or "").strip()
    main = _clean_lot_number(row.get("MNO"))
    sub = _clean_lot_number(row.get("SNO"))
    lot = ""
    if main:
        lot = main if not sub or sub == "0" else f"{main}-{sub}"
    return " ".join(piece for piece in ("서울특별시", district, dong, lot) if piece)


def _house_type(row: dict) -> tuple[schema.HouseType, str]:
    usage = str(row.get("BLDG_USG") or "주택").strip()
    area = _to_float(row.get("RENT_AREA"))
    if usage == "아파트":
        return "apartment", usage
    if usage == "오피스텔":
        return "officetel", usage
    if area < 33:
        return "one_room", usage
    if area < 60:
        return "two_plus", usage
    return "house", usage


def _normalize(row: dict) -> schema.RentTransaction:
    deposit = _to_int(row.get("GRFE"))
    monthly_rent = _to_int(row.get("RTFE"))
    contract_raw = str(row.get("CTRT_DAY") or "").strip()
    contract_date = (
        f"{contract_raw[:4]}-{contract_raw[4:6]}-{contract_raw[6:8]}"
        if len(contract_raw) == 8
        else contract_raw
    )
    house_type, house_type_label = _house_type(row)
    address = _address(row)
    identity = "|".join(
        str(row.get(key) or "")
        for key in ("CTRT_DAY", "CGG_CD", "STDG_CD", "MNO", "SNO", "FLR", "GRFE", "RTFE")
    )
    building_name = str(row.get("BLDG_NM") or "").strip() or None
    return schema.RentTransaction(
        id=hashlib.sha1(identity.encode("utf-8")).hexdigest()[:16],
        district=str(row.get("CGG_NM") or "").strip(),
        dong=str(row.get("STDG_NM") or "").strip(),
        building_name=building_name,
        address=address,
        rent_type="monthly" if monthly_rent > 0 else "jeonse",
        deposit=deposit,
        monthly_rent=monthly_rent,
        area_m2=round(_to_float(row.get("RENT_AREA")), 2),
        floor=_to_int(row.get("FLR")) if row.get("FLR") not in (None, "") else None,
        contract_date=contract_date,
        house_type=house_type,
        house_type_label=house_type_label,
        build_year=_to_int(row.get("ARCH_YR")) or None,
    )


def _geocode(address: str) -> tuple[float, float] | None:
    if not settings.NAVER_MAPS_API_KEY_ID or not settings.NAVER_MAPS_API_KEY_SECRET:
        return None

    now = time.monotonic()
    with _geocode_lock:
        cached = _geocode_cache.get(address)
        if cached and cached[0] > now:
            return cached[1]

    url = f"{NAVER_GEOCODE_API}?{urlencode({'query': address})}"
    data = _fetch_json(
        url,
        headers={
            "Accept": "application/json",
            "x-ncp-apigw-api-key-id": settings.NAVER_MAPS_API_KEY_ID,
            "x-ncp-apigw-api-key": settings.NAVER_MAPS_API_KEY_SECRET,
        },
    )
    addresses = data.get("addresses") or []
    coordinate = None
    if addresses:
        coordinate = (_to_float(addresses[0].get("y")), _to_float(addresses[0].get("x")))

    with _geocode_lock:
        _geocode_cache[address] = (now + GEOCODE_TTL_SECONDS, coordinate)
    return coordinate


def _seoul_rows(district: str, year: int, requested_limit: int) -> tuple[list[dict], str]:
    district_code = DISTRICT_CODES.get(district)
    if not district_code:
        raise HTTPException(status_code=400, detail="서울특별시 자치구만 조회할 수 있습니다.")

    api_key = settings.SEOUL_OPEN_DATA_API_KEY.strip() or "sample"
    end_index = 5 if api_key == "sample" else min(max(requested_limit * 3, 200), 1000)
    path = "/".join(
        quote(str(part), safe="")
        for part in (api_key, "json", "tbLnOpendataRentV", 1, end_index, year, district_code, district)
    )
    data = _fetch_json(f"{SEOUL_RENT_API}/{path}/")
    payload = data.get("tbLnOpendataRentV") or {}
    result = payload.get("RESULT") or {}
    code = result.get("CODE")
    if code not in (None, "INFO-000", "INFO-200"):
        raise HTTPException(status_code=502, detail=result.get("MESSAGE") or "서울시 API 요청에 실패했습니다.")
    return payload.get("row") or [], "seoul_sample" if api_key == "sample" else "seoul_open_data"


def _matches_house_type(item: schema.RentTransaction, house_type: str) -> bool:
    return house_type == "all" or item.house_type == house_type


def list_rent_transactions(
    *,
    district: str,
    dong: str | None,
    q: str | None,
    rent_type: str,
    house_type: str,
    deposit_max: int | None,
    monthly_rent_max: int | None,
    year: int,
    south: float | None,
    north: float | None,
    west: float | None,
    east: float | None,
    limit: int,
) -> schema.RentTransactionListResponse:
    rows, source = _seoul_rows(district.strip(), year, limit)
    items = [_normalize(row) for row in rows]
    normalized_query = (q or "").strip().casefold()
    normalized_dong = (dong or "").strip()

    items = [
        item
        for item in items
        if item.district == district.strip()
        and (not normalized_dong or normalized_dong in item.dong)
        and (
            not normalized_query
            or normalized_query in item.dong.casefold()
            or normalized_query in (item.building_name or "").casefold()
            or normalized_query in item.address.casefold()
        )
        and (rent_type == "all" or item.rent_type == rent_type)
        and _matches_house_type(item, house_type)
        and (deposit_max is None or item.deposit <= deposit_max)
        and (monthly_rent_max is None or item.monthly_rent <= monthly_rent_max)
    ]

    unique_addresses = list(dict.fromkeys(item.address for item in items))[:MAX_GEOCODES_PER_REQUEST]
    coordinates = {address: _geocode(address) for address in unique_addresses}
    for item in items:
        coordinate = coordinates.get(item.address)
        if coordinate:
            item.lat, item.lng = coordinate

    has_bounds = None not in (south, north, west, east)
    if has_bounds:
        items = [
            item
            for item in items
            if item.lat is not None
            and item.lng is not None
            and south <= item.lat <= north
            and west <= item.lng <= east
        ]

    items.sort(key=lambda item: item.contract_date, reverse=True)
    items = items[:limit]
    return schema.RentTransactionListResponse(
        items=items,
        total=len(items),
        source=source,
        geocoded_count=sum(item.lat is not None and item.lng is not None for item in items),
        notice=(
            "SEOUL_OPEN_DATA_API_KEY가 없어 서울시 공식 샘플 5건만 표시합니다."
            if source == "seoul_sample"
            else None
        ),
    )
