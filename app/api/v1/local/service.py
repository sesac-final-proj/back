import json
import math
from concurrent.futures import ThreadPoolExecutor
from urllib.error import URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.v1.local import schema
from app.core.config import settings
from app.models.region import Region


def list_regions(db: Session) -> schema.RegionListResponse:
    regions = db.query(Region).order_by(Region.gu_name, Region.dong_name).all()
    return schema.RegionListResponse(items=[schema.RegionItem.model_validate(r) for r in regions])


KAKAO_KEYWORD_SEARCH_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"
SEOUL_CITYDATA_BASE = "http://openapi.seoul.go.kr:8088"
RECOMMEND_RADIUS_METERS = 2000
RECOMMEND_MAX_RESULTS = 5

# 서울시 실시간 도시데이터 공식 명소 121곳 (프론트 GajiMap.tsx와 동일 목록).
SPOTS: list[dict[str, object]] = [
    {"name": "강남 MICE 관광특구", "lat": 37.511, "lng": 127.060063},
    {"name": "동대문 관광특구", "lat": 37.567311, "lng": 127.011023},
    {"name": "명동 관광특구", "lat": 37.564149, "lng": 126.981851},
    {"name": "이태원 관광특구", "lat": 37.534438, "lng": 126.994373},
    {"name": "잠실 관광특구", "lat": 37.516479, "lng": 127.115274},
    {"name": "종로·청계 관광특구", "lat": 37.570002, "lng": 126.99737},
    {"name": "홍대 관광특구", "lat": 37.553919, "lng": 126.921274},
    {"name": "경복궁", "lat": 37.579876, "lng": 126.976765},
    {"name": "광화문·덕수궁", "lat": 37.569429, "lng": 126.976694},
    {"name": "보신각", "lat": 37.570585, "lng": 126.983411},
    {"name": "서울 암사동 유적", "lat": 37.560632, "lng": 127.130759},
    {"name": "창덕궁·종묘", "lat": 37.578848, "lng": 126.993719},
    {"name": "가산디지털단지역", "lat": 37.48074, "lng": 126.882414},
    {"name": "강남역", "lat": 37.498428, "lng": 127.027961},
    {"name": "건대입구역", "lat": 37.540411, "lng": 127.069418},
    {"name": "고덕역", "lat": 37.555239, "lng": 127.154133},
    {"name": "고속터미널역", "lat": 37.505086, "lng": 127.004456},
    {"name": "교대역", "lat": 37.493489, "lng": 127.014234},
    {"name": "구로디지털단지역", "lat": 37.484852, "lng": 126.901594},
    {"name": "구로역", "lat": 37.502931, "lng": 126.881452},
    {"name": "군자역", "lat": 37.557161, "lng": 127.079549},
    {"name": "대림역", "lat": 37.49308, "lng": 126.895315},
    {"name": "동대문역", "lat": 37.571439, "lng": 127.010156},
    {"name": "뚝섬역", "lat": 37.547141, "lng": 127.047402},
    {"name": "미아사거리역", "lat": 37.613385, "lng": 127.030026},
    {"name": "발산역", "lat": 37.558597, "lng": 126.837895},
    {"name": "사당역", "lat": 37.476906, "lng": 126.981604},
    {"name": "삼각지역", "lat": 37.534899, "lng": 126.973169},
    {"name": "서울대입구역", "lat": 37.48118, "lng": 126.952758},
    {"name": "서울식물원·마곡나루역", "lat": 37.567746, "lng": 126.834017},
    {"name": "서울역", "lat": 37.554648, "lng": 126.970633},
    {"name": "선릉역", "lat": 37.504487, "lng": 127.048956},
    {"name": "성신여대입구역", "lat": 37.592659, "lng": 127.016629},
    {"name": "수유역", "lat": 37.637508, "lng": 127.025624},
    {"name": "숭례문", "lat": 37.559639, "lng": 126.975306},
    {"name": "시의회 앞", "lat": 37.567007, "lng": 126.976587},
    {"name": "신논현역·논현역", "lat": 37.506922, "lng": 127.023871},
    {"name": "신도림역", "lat": 37.508931, "lng": 126.890695},
    {"name": "신림역", "lat": 37.48429, "lng": 126.929631},
    {"name": "신정네거리역", "lat": 37.520138, "lng": 126.853037},
    {"name": "신촌·이대역", "lat": 37.556754, "lng": 126.940348},
    {"name": "쌍문역", "lat": 37.648356, "lng": 127.034724},
    {"name": "양재역", "lat": 37.484439, "lng": 127.034458},
    {"name": "역삼역", "lat": 37.500645, "lng": 127.036495},
    {"name": "연신내역", "lat": 37.618957, "lng": 126.920951},
    {"name": "오목교역·목동운동장", "lat": 37.527393, "lng": 126.875323},
    {"name": "왕십리역", "lat": 37.561266, "lng": 127.037135},
    {"name": "용산역", "lat": 37.52989, "lng": 126.964771},
    {"name": "이태원역", "lat": 37.534571, "lng": 126.994119},
    {"name": "잠실새내역", "lat": 37.511677, "lng": 127.085023},
    {"name": "잠실역", "lat": 37.513264, "lng": 127.100134},
    {"name": "장지역", "lat": 37.478643, "lng": 127.126233},
    {"name": "장한평역", "lat": 37.561439, "lng": 127.064539},
    {"name": "천호역", "lat": 37.538622, "lng": 127.123512},
    {"name": "총신대입구(이수)역", "lat": 37.486445, "lng": 126.982236},
    {"name": "충정로역", "lat": 37.559828, "lng": 126.963493},
    {"name": "합정역", "lat": 37.549504, "lng": 126.913876},
    {"name": "혜화역", "lat": 37.582264, "lng": 127.001859},
    {"name": "홍대입구역(2호선)", "lat": 37.556885, "lng": 126.923793},
    {"name": "회기역", "lat": 37.589839, "lng": 127.057989},
    {"name": "가락시장", "lat": 37.492813, "lng": 127.111451},
    {"name": "가로수길", "lat": 37.519702, "lng": 127.023157},
    {"name": "광장(전통)시장", "lat": 37.570146, "lng": 126.999719},
    {"name": "김포공항", "lat": 37.562095, "lng": 126.801538},
    {"name": "남대문시장", "lat": 37.559239, "lng": 126.977611},
    {"name": "노량진", "lat": 37.513511, "lng": 126.940912},
    {"name": "덕수궁길·정동길", "lat": 37.566373, "lng": 126.971261},
    {"name": "북창동 먹자골목", "lat": 37.562729, "lng": 126.978255},
    {"name": "북촌한옥마을", "lat": 37.582575, "lng": 126.983574},
    {"name": "서촌", "lat": 37.579978, "lng": 126.970868},
    {"name": "성수카페거리", "lat": 37.542289, "lng": 127.054359},
    {"name": "송리단길·호수단길", "lat": 37.510344, "lng": 127.108422},
    {"name": "신촌 스타광장", "lat": 37.558359, "lng": 126.936855},
    {"name": "압구정로데오거리", "lat": 37.526848, "lng": 127.038891},
    {"name": "여의도", "lat": 37.525546, "lng": 126.924794},
    {"name": "연남동", "lat": 37.562588, "lng": 126.923835},
    {"name": "영등포 타임스퀘어", "lat": 37.517229, "lng": 126.903829},
    {"name": "용리단길", "lat": 37.531238, "lng": 126.972322},
    {"name": "이태원 앤틱가구거리", "lat": 37.533869, "lng": 126.994272},
    {"name": "익선동", "lat": 37.574421, "lng": 126.989718},
    {"name": "인사동", "lat": 37.574139, "lng": 126.984812},
    {"name": "잠실롯데타워·석촌호수", "lat": 37.512644, "lng": 127.102656},
    {"name": "청담동 명품거리", "lat": 37.526438, "lng": 127.046524},
    {"name": "창동 신경제 중심지", "lat": 37.653148, "lng": 127.047812},
    {"name": "청량리 제기동 일대 전통시장", "lat": 37.581561, "lng": 127.041695},
    {"name": "해방촌·경리단길", "lat": 37.541459, "lng": 126.987762},
    {"name": "DMC(디지털미디어시티)", "lat": 37.579482, "lng": 126.889912},
    {"name": "DDP(동대문디자인플라자)", "lat": 37.566512, "lng": 127.009024},
    {"name": "강서한강공원", "lat": 37.588829, "lng": 126.815248},
    {"name": "고척돔", "lat": 37.498218, "lng": 126.867119},
    {"name": "광나루한강공원", "lat": 37.548912, "lng": 127.120719},
    {"name": "광화문광장", "lat": 37.572412, "lng": 126.976912},
    {"name": "국립중앙박물관·용산가족공원", "lat": 37.523812, "lng": 126.980312},
    {"name": "난지한강공원", "lat": 37.566112, "lng": 126.878812},
    {"name": "남산공원", "lat": 37.550912, "lng": 126.991012},
    {"name": "노들섬", "lat": 37.517612, "lng": 126.958212},
    {"name": "뚝섬한강공원", "lat": 37.529312, "lng": 127.070112},
    {"name": "망원한강공원", "lat": 37.555512, "lng": 126.896712},
    {"name": "반포한강공원", "lat": 37.510312, "lng": 126.996012},
    {"name": "보라매공원", "lat": 37.492712, "lng": 126.919712},
    {"name": "북서울꿈의숲", "lat": 37.621812, "lng": 127.041812},
    {"name": "서대문독립공원", "lat": 37.574412, "lng": 126.957212},
    {"name": "서리풀공원·몽마르뜨공원", "lat": 37.497512, "lng": 127.004112},
    {"name": "서울대공원", "lat": 37.427812, "lng": 127.017012},
    {"name": "서울숲공원", "lat": 37.544412, "lng": 127.037412},
    {"name": "송현녹지광장", "lat": 37.575612, "lng": 126.983112},
    {"name": "아차산", "lat": 37.552412, "lng": 127.098812},
    {"name": "안양천", "lat": 37.516812, "lng": 126.883412},
    {"name": "양화한강공원", "lat": 37.538512, "lng": 126.899812},
    {"name": "어린이대공원", "lat": 37.549912, "lng": 127.081312},
    {"name": "여의도한강공원", "lat": 37.528412, "lng": 126.932912},
    {"name": "여의서로", "lat": 37.531212, "lng": 126.918912},
    {"name": "올림픽공원", "lat": 37.520612, "lng": 127.121412},
    {"name": "월드컵공원", "lat": 37.563812, "lng": 126.891212},
    {"name": "응봉산", "lat": 37.548912, "lng": 127.032112},
    {"name": "이촌한강공원", "lat": 37.516812, "lng": 126.970812},
    {"name": "잠실종합운동장", "lat": 37.514812, "lng": 127.073612},
    {"name": "잠실한강공원", "lat": 37.517812, "lng": 127.082112},
    {"name": "잠원한강공원", "lat": 37.520812, "lng": 127.011812},
    {"name": "청계산", "lat": 37.445612, "lng": 127.054312},
    {"name": "홍제폭포", "lat": 37.584212, "lng": 126.936212},
]

_CONGEST_RANK = {"붐빔": 4, "약간 붐빔": 3, "보통": 2}


def _congest_rank(level: str) -> int:
    return _CONGEST_RANK.get(level, 1)  # 여유/쾌적/정보없음은 전부 최하위 취급


def _distance_meters(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371000
    d_lat = math.radians(lat2 - lat1)
    d_lng = math.radians(lng2 - lng1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lng / 2) ** 2
    )
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _geocode_query(query: str) -> tuple[float, float] | None:
    url = f"{KAKAO_KEYWORD_SEARCH_URL}?{urlencode({'query': query})}"
    request = Request(url, headers={"Authorization": f"KakaoAK {settings.KAKAO_REST_API_KEY}"}, method="GET")
    try:
        with urlopen(request, timeout=8) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (OSError, URLError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="장소 검색에 실패했습니다."
        ) from exc

    documents = data.get("documents") or []
    if not documents:
        return None
    first = documents[0]
    return float(first["y"]), float(first["x"])  # (lat, lng)


def _fetch_congestion(name: str) -> tuple[str, str | None]:
    url = f"{SEOUL_CITYDATA_BASE}/{settings.SEOUL_CITYDATA_API_KEY}/json/citydata/1/5/{quote(name)}"
    try:
        with urlopen(url, timeout=8) as response:
            data = json.loads(response.read().decode("utf-8"))
        # 서울시 citydata API 응답의 실제 최상위 키는 "CITYDATA"다
        # ("SeoulRtd.citydata"로 오는 문서/버전도 있다는 얘기가 있어 방어적으로 둘 다 확인).
        citydata = data.get("CITYDATA") or data.get("SeoulRtd.citydata") or {}
        live = citydata.get("LIVE_PPLTN_STTS") or []
        if isinstance(live, dict):
            live = [live]
        first = live[0]
        level = first.get("AREA_CONGEST_LVL") or "정보없음"
        message = first.get("AREA_CONGEST_MSG")
        return level, message
    except (OSError, URLError, json.JSONDecodeError, IndexError, AttributeError, TypeError, KeyError):
        # 명소 하나의 혼잡도 조회가 실패해도 전체 추천 결과 자체는 계속 내려준다.
        return "정보없음", None


def _compact(value: object, limit: int = 82) -> str:
    content = str(value or "").strip()
    if len(content) <= limit:
        return content
    return f"{content[: limit - 1]}..."


def _format_summary(risk_type: str | None, address: str | None, description: str | None) -> str:
    pieces = [_compact(risk_type, 32), _compact(address, 58), _compact(description, 82)]
    summary = " · ".join(piece for piece in pieces if piece)
    return summary or "서울안전누리 위험신호"


def list_danger_signals(
    db: Session,
    sigungu: str | None,
    q: str | None,
    limit: int,
) -> schema.DangerSignalListResponse:
    filters = [
        "source = 'seoul_safecity'",
        "latitude is not null",
        "longitude is not null",
    ]
    params: dict[str, object] = {"limit": limit}

    if sigungu:
        filters.append(
            """
            (
              sigungu = :sigungu
              or raw_data->'matched_districts' ? :sigungu
              or address ilike :sigungu_like
              or risk_name ilike :sigungu_like
              or description ilike :sigungu_like
            )
            """
        )
        params["sigungu"] = sigungu
        params["sigungu_like"] = f"%{sigungu}%"

    if q:
        filters.append(
            """
            (
              risk_name ilike :q
              or risk_type ilike :q
              or address ilike :q
              or description ilike :q
            )
            """
        )
        params["q"] = f"%{q}%"

    where_clause = " and ".join(f"({part})" for part in filters)
    rows = db.execute(
        text(
            f"""
            select
              coalesce(external_id, id::text) as id,
              risk_type,
              risk_name,
              address,
              coalesce(sigungu, raw_data->'matched_districts'->>0) as sigungu,
              latitude,
              longitude,
              description,
              observed_at,
              source_url
            from public.nuri_crawled
            where {where_clause}
            order by coalesce(observed_at, crawled_at) desc nulls last, id desc
            limit :limit
            """
        ),
        params,
    ).mappings().all()

    items = [
        schema.DangerSignalItem(
            id=str(row["id"]),
            name=_compact(row["risk_name"] or row["address"] or row["risk_type"] or "서울안전누리 위험신호", 80),
            neighborhood_name=row["sigungu"],
            sigungu=row["sigungu"],
            distance="실시간",
            summary=_format_summary(row["risk_type"], row["address"], row["description"]),
            lat=float(row["latitude"]),
            lng=float(row["longitude"]),
            risk_type=row["risk_type"],
            observed_at=row["observed_at"],
            source_url=row["source_url"],
        )
        for row in rows
    ]

    return schema.DangerSignalListResponse(items=items, total=len(items))


def recommend_place(query: str) -> schema.PlaceRecommendationResponse:
    coords = _geocode_query(query)
    if coords is None:
        return schema.PlaceRecommendationResponse(results=[])
    lat, lng = coords

    candidates = []
    for spot in SPOTS:
        distance = _distance_meters(lat, lng, spot["lat"], spot["lng"])
        if distance <= RECOMMEND_RADIUS_METERS:
            candidates.append((distance, spot))
    candidates.sort(key=lambda pair: pair[0])

    if not candidates:
        return schema.PlaceRecommendationResponse(results=[])

    # 혼잡도 조회 실패(정보없음)인 후보를 최종 5개에서 제외해도 채울 수 있도록,
    # 반경 내 후보 전체를 대상으로 조회한다 (조회는 서로 독립적이라 병렬 처리).
    with ThreadPoolExecutor(max_workers=len(candidates)) as executor:
        congestions = list(executor.map(lambda pair: _fetch_congestion(pair[1]["name"]), candidates))

    results = [
        schema.PlaceRecommendation(
            name=spot["name"],
            lat=spot["lat"],
            lng=spot["lng"],
            distanceMeters=round(distance),
            congestionLevel=level,
            congestionMessage=message,
        )
        for (distance, spot), (level, message) in zip(candidates, congestions)
        if level != "정보없음"  # 혼잡도 조회 실패 — 추천 의미가 없어 제외
    ]
    # 혼잡도 높은 순 우선, 같은 등급이면 가까운 곳 우선.
    results.sort(key=lambda item: (-_congest_rank(item.congestionLevel), item.distanceMeters))
    return schema.PlaceRecommendationResponse(results=results[:RECOMMEND_MAX_RESULTS])
