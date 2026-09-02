import unittest
from unittest.mock import patch

from app.api.v1.real_estate import service
from app.core.config import settings


SAMPLE_ROWS = [
    {
        "RCPT_YR": "2026",
        "CGG_CD": "11710",
        "CGG_NM": "송파구",
        "STDG_CD": "10800",
        "STDG_NM": "문정동",
        "MNO": "0652",
        "SNO": "0004",
        "FLR": 14.0,
        "CTRT_DAY": "20260831",
        "RENT_SE": "월세",
        "RENT_AREA": 17.93,
        "GRFE": "15700",
        "RTFE": "18",
        "BLDG_NM": "힐스테이트에코문정",
        "ARCH_YR": "2018",
        "BLDG_USG": "오피스텔",
    },
    {
        "RCPT_YR": "2026",
        "CGG_CD": "11710",
        "CGG_NM": "송파구",
        "STDG_CD": "10100",
        "STDG_NM": "잠실동",
        "MNO": "0022",
        "SNO": "0000",
        "FLR": 20.0,
        "CTRT_DAY": "20260830",
        "RENT_SE": "전세",
        "RENT_AREA": 59.99,
        "GRFE": "93713",
        "RTFE": "0",
        "BLDG_NM": "리센츠",
        "ARCH_YR": "2008",
        "BLDG_USG": "아파트",
    },
]


class RealEstateApiTest(unittest.TestCase):
    def setUp(self):
        self.original_seoul_key = settings.SEOUL_OPEN_DATA_API_KEY
        settings.SEOUL_OPEN_DATA_API_KEY = "test-key"

    def tearDown(self):
        settings.SEOUL_OPEN_DATA_API_KEY = self.original_seoul_key

    @patch("app.api.v1.real_estate.service._geocode", return_value=(37.485, 127.122))
    @patch("app.api.v1.real_estate.service._fetch_json")
    def test_normalizes_and_filters_monthly_rent(self, fetch_json, _geocode):
        fetch_json.return_value = {
            "tbLnOpendataRentV": {
                "RESULT": {"CODE": "INFO-000", "MESSAGE": "정상 처리되었습니다"},
                "row": SAMPLE_ROWS,
            }
        }

        response = service.list_rent_transactions(
            district="송파구",
            dong=None,
            q=None,
            rent_type="monthly",
            house_type="officetel",
            deposit_max=None,
            monthly_rent_max=None,
            year=2026,
            south=None,
            north=None,
            west=None,
            east=None,
            limit=160,
        )

        self.assertEqual(response.total, 1)
        self.assertEqual(response.items[0].building_name, "힐스테이트에코문정")
        self.assertEqual(response.items[0].rent_type, "monthly")
        self.assertEqual(response.items[0].address, "서울특별시 송파구 문정동 652-4")
        self.assertEqual(response.items[0].lat, 37.485)

    @patch("app.api.v1.real_estate.service._geocode", return_value=None)
    @patch("app.api.v1.real_estate.service._fetch_json")
    def test_rejects_non_seoul_district_and_supports_jeonse(self, fetch_json, _geocode):
        with self.assertRaises(Exception) as context:
            service.list_rent_transactions(
                district="수원시",
                dong=None,
                q=None,
                rent_type="monthly",
                house_type="all",
                deposit_max=None,
                monthly_rent_max=None,
                year=2026,
                south=None,
                north=None,
                west=None,
                east=None,
                limit=160,
            )
        self.assertEqual(context.exception.status_code, 400)

        fetch_json.return_value = {
            "tbLnOpendataRentV": {"RESULT": {"CODE": "INFO-000"}, "row": SAMPLE_ROWS}
        }
        response = service.list_rent_transactions(
            district="송파구",
            dong=None,
            q=None,
            rent_type="jeonse",
            house_type="all",
            deposit_max=100000,
            monthly_rent_max=None,
            year=2026,
            south=None,
            north=None,
            west=None,
            east=None,
            limit=160,
        )
        self.assertEqual(response.items[0].building_name, "리센츠")


if __name__ == "__main__":
    unittest.main()
