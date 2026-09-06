import hashlib
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
    rows, source = _rows(district)
    child_rows = [
        row
        for row in rows
        if "아동" in f"{row.get('FCLT_KIND_NM', '')} {row.get('FCLT_KIND_DTL_NM', '')}"
        and district in str(row.get("FCLT_ADDR") or "")
    ][:limit]

    items = []
    for row in child_rows:
        name = str(row.get("FCLT_NM") or "").strip()
        address = str(row.get("FCLT_ADDR") or "").strip()
        coordinate = _geocode(address)
        identity = str(row.get("FCLT_CD") or f"{name}|{address}")
        items.append(
            schema.FacilityItem(
                id=hashlib.sha1(identity.encode("utf-8")).hexdigest()[:16],
                name=name,
                district=district,
                facility_type=str(row.get("FCLT_KIND_NM") or "아동복지시설").strip(),
                address=address,
                phone=str(row.get("FCLT_TEL_NO") or "").strip() or None,
                lat=coordinate[0] if coordinate else None,
                lng=coordinate[1] if coordinate else None,
            )
        )

    return schema.FacilityListResponse(
        items=items,
        total=len(items),
        geocoded_count=sum(item.lat is not None and item.lng is not None for item in items),
        source=source,
        notice="서울 열린데이터 샘플 5건만 조회합니다." if source == "seoul_sample" else None,
    )
