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

    def test_rejects_unsupported_district(self):
        with self.assertRaises(HTTPException):
            service.list_facilities("수원시", 50)

if __name__ == "__main__":
    unittest.main()
