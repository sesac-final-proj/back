"""Region 시드 스크립트: python -m scripts.seed_regions

dong_code는 아직 행정표준코드 마스터 데이터를 안 들여왔어서 임시 값이다.
실제 행정동 코드 데이터가 준비되면 SAMPLE_REGIONS를 교체하면 된다.
"""

from app.core.db import SessionLocal
from app.models.region import Region

SAMPLE_REGIONS = [
    {"dong_code": "TMP-YDP-001", "dong_name": "영등포구 여의동", "lat": 37.5219, "lng": 126.9245},
    {"dong_code": "TMP-NW-001", "dong_name": "노원구 상계동", "lat": 37.6597, "lng": 127.0700},
    {"dong_code": "TMP-SPA-001", "dong_name": "송파구 잠실동", "lat": 37.5133, "lng": 127.1000},
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
