import csv
import hashlib
import json
from pathlib import Path
from urllib.parse import quote

from fastapi import HTTPException, status

from app.api.v1.dream import schema
from app.api.v1.real_estate.service import _fetch_json, _geocode
from app.core.config import settings

DISTRICT_SERVICES = {
    "강남구": "fcltOpenInfo_GN",
    "강동구": "fcltOpenInfo_GD",
    "강북구": "fcltOpenInfo_GB",
    "강서구": "fcltOpenInfo_GS",
    "관악구": "fcltOpenInfo_GA",
    "광진구": "fcltOpenInfo_GJ",
    "구로구": "fcltOpenInfo_GR",
    "금천구": "fcltOpenInfo_GC",
    "노원구": "fcltOpenInfo_NW",
    "도봉구": "fcltOpenInfo_DB",
    "동대문구": "fcltOpenInfo_DD",
    "동작구": "fcltOpenInfo_DJ",
    "마포구": "fcltOpenInfo_MP",
    "서대문구": "fcltOpenInfo_SM",
    "서초구": "fcltOpenInfo_SC",
    "성동구": "fcltOpenInfo_SD",
    "성북구": "fcltOpenInfo_SB",
    "송파구": "fcltOpenInfo_SP",
    "양천구": "fcltOpenInfo_YC",
    "영등포구": "fcltOpenInfo_YD",
    "용산구": "fcltOpenInfo_YS",
    "은평구": "fcltOpenInfo_EP",
    "종로구": "fcltOpenInfo_JN",
    "중구": "fcltOpenInfo_JG",
    "중랑구": "fcltOpenInfo_JR",
}

DISTRICT_DEFAULT_COORDS: dict[str, tuple[float, float]] = {
    "강남구": (37.5172, 127.0473),
    "강동구": (37.5301, 127.1238),
    "강북구": (37.6396, 127.0257),
    "강서구": (37.5509, 126.8495),
    "관악구": (37.4784, 126.9516),
    "광진구": (37.5385, 127.0822),
    "구로구": (37.4954, 126.8874),
    "금천구": (37.4568, 126.8955),
    "노원구": (37.6542, 127.0568),
    "도봉구": (37.6688, 127.0471),
    "동대문구": (37.5744, 127.0400),
    "동작구": (37.5124, 126.9393),
    "마포구": (37.5663, 126.9016),
    "서대문구": (37.5791, 126.9368),
    "서초구": (37.4837, 127.0324),
    "성동구": (37.5635, 127.0369),
    "성북구": (37.5894, 127.0167),
    "송파구": (37.5145, 127.1060),
    "양천구": (37.5169, 126.8665),
    "영등포구": (37.5264, 126.8963),
    "용산구": (37.5326, 126.9900),
    "은평구": (37.6027, 126.9291),
    "종로구": (37.5730, 126.9794),
    "중구": (37.5641, 126.9979),
    "중랑구": (37.6066, 127.0927),
}

PROJECT_ROOT = Path(__file__).resolve().parents[5]
CSV_PATH = PROJECT_ROOT / "back" / "data" / "dream_child_facilities.csv"
if not CSV_PATH.exists():
    CSV_PATH = PROJECT_ROOT / "data" / "dream_child_facilities.csv"

JSON_412_PATH = PROJECT_ROOT / "all_seoul_centers_412.json"
JSON_PARSED_PATH = PROJECT_ROOT / "all_districts_parsed.json"

OFFICIAL_FACILITY_URL = "https://umppa.seoul.go.kr/icare/user/fcltyInfoManage/BD_selectFcltyInfoManage.do"


def _load_412_centers() -> list[dict]:
    if not JSON_412_PATH.exists():
        return []
    try:
        with JSON_412_PATH.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _load_parsed_centers() -> dict[str, list[dict]]:
    if not JSON_PARSED_PATH.exists():
        return {}
    try:
        with JSON_PARSED_PATH.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _csv_rows(district: str) -> list[dict[str, str]]:
    if not CSV_PATH.exists():
        return []

    rows: list[dict[str, str]] = []
    for enc in ("cp949", "euc-kr", "utf-8-sig", "utf-8"):
        try:
            with CSV_PATH.open("r", encoding=enc, newline="") as file:
                rows = list(csv.DictReader(file))
                if rows:
                    break
        except (UnicodeDecodeError, UnicodeError):
            continue

    matched = []
    for row in rows:
        address = row.get("소재지전체주소") or row.get("도로명전체주소") or ""
        status_str = (row.get("영업상태명") or "").strip()
        if district in address and ("운영" in status_str or status_str in ("운영", "운영중")):
            matched.append(row)
    return matched


def _rows(district: str) -> tuple[list[dict], str]:
    service_name = DISTRICT_SERVICES.get(district)
    if not service_name:
        raise HTTPException(status_code=400, detail="지원하지 않는 자치구입니다.")

    api_key = (settings.SEOUL_OPEN_DATA_API_KEY or settings.SEOUL_OPEN_API_KEY).strip() or "sample"
    end_index = 5 if api_key == "sample" else 1000
    path = "/".join(quote(str(part), safe="") for part in (api_key, "json", service_name, 1, end_index))
    data = _fetch_json(f"{settings.SEOUL_OPEN_API_BASE_URL}/{path}/")
    payload = data.get(service_name) or {}
    result = payload.get("RESULT") or data.get("RESULT") or {}
    if result.get("CODE") not in (None, "INFO-000", "INFO-200"):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=result.get("MESSAGE") or "서울시 시설 API 요청에 실패했습니다.",
        )
    return payload.get("row") or [], "seoul_sample" if api_key == "sample" else "seoul_open_data"


def list_facilities(district: str, limit: int) -> schema.FacilityListResponse:
    district = district.strip()
    centers_412 = _load_412_centers()
    default_lat, default_lng = DISTRICT_DEFAULT_COORDS.get(district, (37.5665, 126.9780))

    csv_rows = _csv_rows(district)
    if csv_rows:
        items = []
        for i, row in enumerate(csv_rows[:limit]):
            address = (row.get("도로명전체주소") or row.get("소재지전체주소") or "").strip()
            name = (row.get("사업장명") or "").strip()
            identity = f"{name}|{address}|{row.get('인허가번호', '')}"

            coordinate = _geocode(address) if address else None
            if coordinate:
                lat, lng = coordinate
            else:
                try:
                    lng = float(row["위치정보(X)"]) if row.get("위치정보(X)") else None
                    lat = float(row["위치정보(Y)"]) if row.get("위치정보(Y)") else None
                except ValueError:
                    lat, lng = None, None

            if lat is None or lng is None:
                # Provide small offset for display so multiple markers don't collapse completely
                offset_lat = (i % 5) * 0.0015
                offset_lng = ((i // 5) % 5) * 0.0015
                lat, lng = default_lat + offset_lat, default_lng + offset_lng

            # Find matching homepage URL from 412 centers if available
            match_412 = next(
                (c for c in centers_412 if c.get("district") == district and (c.get("name") in name or name in c.get("name"))),
                None,
            )
            homepage_url = match_412.get("detail_url") if match_412 else OFFICIAL_FACILITY_URL

            items.append(
                schema.FacilityItem(
                    id=hashlib.sha1(identity.encode("utf-8")).hexdigest()[:16],
                    name=name,
                    district=district,
                    facility_type=(row.get("복지시설종류명") or "아동복지시설").strip(),
                    address=address,
                    homepage_url=homepage_url,
                    established_date=(row.get("인허가일자") or "").strip() or None,
                    operation_status=(row.get("영업상태명") or "").strip() or None,
                    lat=lat,
                    lng=lng,
                )
            )
        return schema.FacilityListResponse(
            items=items,
            total=len(items),
            geocoded_count=sum(item.lat is not None and item.lng is not None for item in items),
            source="csv",
            notice="서울특별시 아동복지시설 정보 CSV 기준입니다.",
        )

    # Fallback to parsed JSON centers (e.g. for districts like 송파구 that are not in CSV)
    parsed_centers = _load_parsed_centers().get(district, [])
    if parsed_centers:
        items = []
        for i, c in enumerate(parsed_centers[:limit]):
            name = c.get("name", "").strip()
            address = c.get("addr", "").strip()
            kind = c.get("kind", "지역아동센터").strip()
            tel = c.get("tel", "").strip() or None
            identity = f"{district}|{name}|{address}"

            coordinate = _geocode(address) if address else None
            if coordinate:
                lat, lng = coordinate
            else:
                offset_lat = (i % 5) * 0.0015
                offset_lng = ((i // 5) % 5) * 0.0015
                lat, lng = default_lat + offset_lat, default_lng + offset_lng

            match_412 = next(
                (center for center in centers_412 if center.get("district") == district and (center.get("name") in name or name in center.get("name"))),
                None,
            )
            homepage_url = match_412.get("detail_url") if match_412 else OFFICIAL_FACILITY_URL

            items.append(
                schema.FacilityItem(
                    id=hashlib.sha1(identity.encode("utf-8")).hexdigest()[:16],
                    name=name,
                    district=district,
                    facility_type=kind,
                    address=address,
                    phone=tel,
                    homepage_url=homepage_url,
                    operation_status="운영중",
                    lat=lat,
                    lng=lng,
                )
            )
        return schema.FacilityListResponse(
            items=items,
            total=len(items),
            geocoded_count=sum(item.lat is not None and item.lng is not None for item in items),
            source="json_412",
            notice="서울특별시 412개 아동복지 센터 데이터 기준입니다.",
        )

    # Open API fallback
    rows, source = _rows(district)
    child_rows = [
        row
        for row in rows
        if "아동" in f"{row.get('FCLT_KIND_NM', '')} {row.get('FCLT_KIND_DTL_NM', '')}"
        and district in str(row.get("FCLT_ADDR") or "")
    ][:limit]

    items = []
    for i, row in enumerate(child_rows):
        name = str(row.get("FCLT_NM") or "").strip()
        address = str(row.get("FCLT_ADDR") or "").strip()
        coordinate = _geocode(address)
        if coordinate:
            lat, lng = coordinate
        else:
            offset_lat = (i % 5) * 0.0015
            offset_lng = ((i // 5) % 5) * 0.0015
            lat, lng = default_lat + offset_lat, default_lng + offset_lng

        identity = str(row.get("FCLT_CD") or f"{name}|{address}")
        homepage_url = next(
            (
                str(row.get(key)).strip()
                for key in ("FCLT_HMPG", "FCLT_HMPG_URL", "FCLT_HOME_URL", "HOMEPAGE")
                if row.get(key)
            ),
            None,
        )
        if not homepage_url and row.get("FCLT_CD"):
            homepage_url = (
                "https://umppa.seoul.go.kr/icare/user/fcltyInfoManage/"
                f"BD_selectFcltyInfoManage.do?q_fcltyId={quote(str(row['FCLT_CD']), safe='')}&q_fclty=1003"
            )
        if not homepage_url:
            homepage_url = OFFICIAL_FACILITY_URL

        items.append(
            schema.FacilityItem(
                id=hashlib.sha1(identity.encode("utf-8")).hexdigest()[:16],
                name=name,
                district=district,
                facility_type=str(row.get("FCLT_KIND_NM") or "아동복지시설").strip(),
                address=address,
                phone=str(row.get("FCLT_TEL_NO") or "").strip() or None,
                homepage_url=homepage_url,
                operation_status=str(row.get("FCLT_STATUS_NM") or "").strip() or None,
                lat=lat,
                lng=lng,
            )
        )

    return schema.FacilityListResponse(
        items=items,
        total=len(items),
        geocoded_count=sum(item.lat is not None and item.lng is not None for item in items),
        source=source,
        notice="서울 열린데이터 샘플 5건만 조회합니다." if source == "seoul_sample" else None,
    )

