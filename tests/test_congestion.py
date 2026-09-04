import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

from app.main import app
from app.api.v1.local.router import list_congestion_zones
from app.local_info import congestion_service as service


SPOTS = [dict(poi='POI001', name='A', lat=37.5, lng=127.0),
         dict(poi='POI002', name='B', lat=37.6, lng=127.1)]
LIVE = dict(AREA_CD='POI001', AREA_NM='A', AREA_CONGEST_LVL='보통',
            AREA_PPLTN_MIN='1,200', AREA_PPLTN_MAX='1500', PPLTN_TIME='2026-09-04 13:00')
BOUNDS = dict(sw_lat=37.49, sw_lng=126.99, ne_lat=37.51, ne_lng=127.01)


class CongestionTest(unittest.TestCase):
    def setUp(self):
        for target, value in [('load_hotspots', None), ('settings', SimpleNamespace(
            SEOUL_CITYDATA_SERVICE='test', SEOUL_OPEN_API_KEY='', SEOUL_OPEN_DATA_API_KEY=''))]:
            mock = patch.object(service, target, return_value=SPOTS) if value is None else patch.object(service, target, value)
            mock.start()
            self.addCleanup(mock.stop)

    def test_registered_route_returns_live_reading_for_heatmap(self):
        with patch.object(service, 'fetch_citydata_ppltn_raw', return_value=LIVE) as fetch:
            zones = list_congestion_zones(**BOUNDS, limit=30)
        fetch.assert_called_once_with('POI001')
        zone = zones[0]
        self.assertEqual(zone['populationMin'], 1200)
        self.assertEqual(zone['source'], 'seoul_citydata_api')
        self.assertEqual(zone['levelLabel'], '보통')
        self.assertEqual(zone['updatedAt'], LIVE['PPLTN_TIME'])
        self.assertNotIn('hourlyTrends', zone)
        self.assertNotIn('baselineScore', zone)
        self.assertIn('/api/v1/local/transit', app.openapi()['paths'])
        self.assertIn('/api/v1/local/congestion-zones', app.openapi()['paths'])

    def test_outside_viewport_does_not_fetch_or_invent_readings(self):
        with patch.object(service, 'fetch_citydata_ppltn_raw') as fetch:
            zones = list_congestion_zones(sw_lat=35, sw_lng=126, ne_lat=36, ne_lng=127, limit=30)
        self.assertEqual(zones, [])
        fetch.assert_not_called()

    def test_missing_or_wrong_area_reading_returns_unavailable(self):
        for reading in (None, {**LIVE, 'AREA_CD': 'POI999'}, {**LIVE, 'AREA_CONGEST_LVL': 'unknown'}):
            with patch.object(service, 'fetch_citydata_ppltn_raw', return_value=reading):
                with self.assertRaises(HTTPException) as raised:
                    list_congestion_zones(**BOUNDS, limit=30)
                self.assertEqual(raised.exception.status_code, 503)

    def test_invalid_viewport_returns_bad_request(self):
        for bounds in ({**BOUNDS, 'sw_lat': 38}, {**BOUNDS, 'sw_lat': float('nan')}, {'sw_lat': 37.5}):
            with self.assertRaises(HTTPException) as raised:
                list_congestion_zones(**bounds, limit=30)
            self.assertEqual(raised.exception.status_code, 400)


class HotspotCatalogTest(unittest.TestCase):
    def test_restored_catalog_has_unique_geographic_locations(self):
        spots = service.load_hotspots()
        self.assertGreater(len(spots), 100)
        self.assertEqual(len(spots), len({spot['poi'] for spot in spots}))
        self.assertTrue(any(spot['poi'] == 'POI074' for spot in spots))
        for spot in spots:
            self.assertTrue(37 < spot['lat'] < 38 and 126 < spot['lng'] < 128)


if __name__ == '__main__':
    unittest.main()
