"""Region 시드 스크립트: python -m scripts.seed_regions

dong_code는 아직 행정표준코드 마스터 데이터를 안 들여왔어서 임시 값이다.
실제 행정동 코드 데이터가 준비되면 SAMPLE_REGIONS를 교체하면 된다.
"""

from app.core.db import SessionLocal
from app.models.region import Region

SAMPLE_REGIONS = [
    {"dong_code": "TMP-YDP-001", "dong_name": "여의동", "gu_name": "영등포구", "lat": 37.5219, "lng": 126.9245},
    {"dong_code": "TMP-NW-001", "dong_name": "상계동", "gu_name": "노원구", "lat": 37.6597, "lng": 127.0700},
    {"dong_code": "TMP-SPA-001", "dong_name": "잠실동", "gu_name": "송파구", "lat": 37.5133, "lng": 127.1000},
]

# data/daangn_영등포구.csv(TASK-02-00 실 데이터)의 "지역" 컬럼에 실제로 등장하는
# 영등포구 소속 동 이름들 — 정확한 위경도 마스터 데이터가 없어 구 대표좌표로
# 통일했다(이 기능에서 위경도는 안 쓰임, 매칭은 dong_name 문자열 일치로만 함).
# "여의동"은 위에 이미 있어 제외. dong_code는 seed_regions.py 컨벤션대로 임시값.
_YDP_CENTER = {"gu_name": "영등포구", "lat": 37.5264, "lng": 126.8962}
_YDP_DONGS = [
    "양평제1동", "신길제1동", "양평제2동", "신길제5동", "도림동", "대림제3동",
    "영등포동", "문래동", "당산제1동", "당산제2동", "영등포구", "여의도동",
    "신길동", "대림동", "대림제1동", "대림제2동", "영등포본동", "당산동",
    "신길제3동", "신길제7동", "신길제6동", "신길제4동",
]
SAMPLE_REGIONS += [
    {"dong_code": f"TMP-YDP-{name}", "dong_name": name, **_YDP_CENTER} for name in _YDP_DONGS
]

# 노원구/송파구는 실거래 데이터가 없어 YDP처럼 크롤링 원본에서 뽑을 수 없다 — 동네
# 검색(regions) 커버리지를 위해 서울시 공식 행정동 목록(위키백과 "○○구의 행정 구역")을
# 그대로 넣는다. 정확한 위경도 마스터가 없는 건 YDP와 동일해서 구 대표좌표로 통일.
# 기존 TMP-NW-001(상계동)/TMP-SPA-001(잠실동)은 실제 행정동 이름이 아닌 임시값이라
# 겹치지 않음 — FK 참조 위험 피하려고 지우지 않고 그대로 둔다.
_NW_CENTER = {"gu_name": "노원구", "lat": 37.6597, "lng": 127.0700}
_NW_DONGS = [
    "공릉1동", "공릉2동", "상계10동", "상계1동", "상계2동", "상계3.4동", "상계5동",
    "상계6.7동", "상계8동", "상계9동", "월계1동", "월계2동", "월계3동", "중계1동",
    "중계2.3동", "중계4동", "중계본동", "하계1동", "하계2동",
]
SAMPLE_REGIONS += [
    {"dong_code": f"TMP-NW-{name}", "dong_name": name, **_NW_CENTER} for name in _NW_DONGS
]

_SPA_CENTER = {"gu_name": "송파구", "lat": 37.5133, "lng": 127.1000}
_SPA_DONGS = [
    "가락1동", "가락2동", "가락본동", "거여1동", "거여2동", "마천1동", "마천2동",
    "문정1동", "문정2동", "방이1동", "방이2동", "삼전동", "석촌동", "송파1동",
    "송파2동", "오금동", "오륜동", "위례동", "잠실2동", "잠실3동", "잠실4동",
    "잠실6동", "잠실7동", "잠실본동", "장지동", "풍납1동", "풍납2동",
]
SAMPLE_REGIONS += [
    {"dong_code": f"TMP-SPA-{name}", "dong_name": name, **_SPA_CENTER} for name in _SPA_DONGS
]

# data/daangn_송파구.csv(실 크롤링 데이터) "지역" 컬럼엔 위 위키백과 현행 행정동
# 목록에 없는 옛 통합동/약칭 표기도 섞여 있다(예: "잠실동"이 "잠실2/3/4/6/7동·
# 잠실본동"과 별도로 등장) — YDP와 동일하게 매칭 실패 방지용으로 그대로 추가.
# "잠실동"은 위 TMP-SPA-001로 이미 있어 제외.
_SPA_LEGACY_DONGS = [
    "문정동", "마천동", "거여동", "풍납동", "신천동", "가락동", "송파동", "방이동",
]
SAMPLE_REGIONS += [
    {"dong_code": f"TMP-SPA-{name}", "dong_name": name, **_SPA_CENTER} for name in _SPA_LEGACY_DONGS
]


def seed():
    db = SessionLocal()
    try:
        for data in SAMPLE_REGIONS:
            exists = db.query(Region).filter_by(dong_code=data["dong_code"]).first()
            if exists:
                continue
            db.add(Region(**data))
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    seed()
    print("regions seeded")
