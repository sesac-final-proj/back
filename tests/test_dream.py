import unittest
from unittest.mock import patch

from fastapi import HTTPException

from app.api.v1.dream import service
from app.core.config import settings


class DreamFacilityApiTest(unittest.TestCase):
    def setUp(self):
        self.original_key = settings.SEOUL_OPEN_DATA_API_KEY
        settings.SEOUL_OPEN_DATA_API_KEY = "test-key"

    def tearDown(self):
        settings.SEOUL_OPEN_DATA_API_KEY = self.original_key

    @patch("app.api.v1.dream.service._geocode", return_value=(37.5, 127.1))
    @patch("app.api.v1.dream.service._fetch_json")
    def test_returns_only_child_facilities_in_district(self, fetch_json, _geocode):
        fetch_json.return_value = {
            "fcltOpenInfo_SP": {
                "RESULT": {"CODE": "INFO-000"},
                "row": [
                    {
                        "FCLT_CD": "A1",
                        "FCLT_NM": "행복지역아동센터",
                        "FCLT_KIND_NM": "(아동복지시설) 지역아동센터",
                        "FCLT_ADDR": "서울특별시 송파구 송파대로 1",
                        "FCLT_TEL_NO": "02-123-4567",
                        "FCLT_HMPG": "https://example.com/happy-center",
                    },
                    {
                        "FCLT_CD": "S1",
                        "FCLT_NM": "어르신센터",
                        "FCLT_KIND_NM": "노인복지시설",
                        "FCLT_ADDR": "서울특별시 송파구 송파대로 2",
                    },
                ],
            }
        }

        response = service.list_facilities("송파구", 50)

        self.assertEqual(response.total, 1)
        self.assertEqual(response.items[0].name, "행복지역아동센터")
        self.assertEqual(response.items[0].lat, 37.5)
        self.assertEqual(response.items[0].homepage_url, "https://example.com/happy-center")

    def test_rejects_unsupported_district(self):
        with self.assertRaises(HTTPException):
            service.list_facilities("수원시", 50)


class DistrictDonationSummaryTest(unittest.TestCase):
    """꿈가지 화면 "기부 참여"/"동네 기부 진행률" — 실 DB에 임시 지역/유저/적립을
    만들었다가 끝나면 지운다. 프론트에 0으로 하드코딩돼 있던 걸 실데이터로 바꾼
    버그 수정의 회귀 테스트."""

    def setUp(self):
        from app.core.db import SessionLocal
        from app.core.security import hash_password
        from app.models.point import PointTransaction
        from app.models.region import Region
        from app.models.user import User, UserRole

        self.db = SessionLocal()
        self.region = Region(
            dong_code="__DREAM_DIST_SC__", dong_name="기부검증동", gu_name="__기부검증구__", lat=0.0, lng=0.0
        )
        self.user = User(
            email="__dream_district_selfcheck__@example.com",
            password_hash=hash_password("x"),
            nickname="dream_district_sc",
            role=UserRole.USER,
        )
        self.db.add_all([self.region, self.user])
        self.db.commit()
        self.db.refresh(self.region)
        self.db.refresh(self.user)
        self.db.add_all(
            [
                PointTransaction(user_id=self.user.id, amount=50, source="general_payment", region_id=self.region.id),
                PointTransaction(user_id=self.user.id, amount=30, source="trade", region_id=self.region.id),
                # 차감 이력은 참여 횟수/모금액에서 빠져야 함(아직 기부 실행 로직은 없지만 방어적으로).
                PointTransaction(user_id=self.user.id, amount=-10, source="trade", region_id=self.region.id),
            ]
        )
        self.db.commit()

    def tearDown(self):
        from app.models.point import PointTransaction

        self.db.query(PointTransaction).filter_by(user_id=self.user.id).delete()
        self.db.delete(self.user)
        self.db.delete(self.region)
        self.db.commit()
        self.db.close()

    def test_counts_only_positive_entries_in_that_district(self):
        summary = service.get_district_donation_summary(self.db, "__기부검증구__")
        self.assertEqual(summary.participation_count, 2)  # +50, +30만 (음수 -10 제외)
        self.assertEqual(summary.total_points, 80)

    def test_no_activity_district_returns_zero(self):
        summary = service.get_district_donation_summary(self.db, "__존재안하는구__")
        self.assertEqual(summary.participation_count, 0)
        self.assertEqual(summary.total_points, 0)

    def test_null_region_id_still_counted_via_fallback_join(self):
        """INNER JOIN이었을 때 재현되던 버그 — region_id가 NULL인 행이 통째로 집계에서
        빠지지 않고 award_points의 기본 지역(영등포구)으로 잡혀야 한다."""
        from app.models.point import PointTransaction

        orphan = PointTransaction(user_id=self.user.id, amount=100, source="general_payment", region_id=None)
        self.db.add(orphan)
        self.db.commit()
        try:
            summary = service.get_district_donation_summary(self.db, service.FALLBACK_REGION_GU_NAME)
            self.assertGreaterEqual(summary.total_points, 100)
        finally:
            self.db.delete(orphan)
            self.db.commit()


if __name__ == "__main__":
    unittest.main()
