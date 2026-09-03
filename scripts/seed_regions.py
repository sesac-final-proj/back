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
