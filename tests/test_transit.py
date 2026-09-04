import time
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException
from app.api.v1.local import transit_service as service


def bike(identifier='ST-1', available='0', lat='37.5', lng='127.1'):
    return {'stationId': identifier, 'stationName': '대여소 ' + identifier,
            'parkingBikeTotCnt': available, 'rackTotCnt': '12',
            'stationLatitude': lat, 'stationLongitude': lng}


class TransitTest(unittest.TestCase):
    def setUp(self):
        service._cache.clear()
        self.settings = patch.object(service, 'settings', SimpleNamespace(
            SEOUL_BIKE_API_KEY='test-key', SEOUL_SUBWAY_API_KEY='test-key',
            SEOUL_OPEN_API_KEY='', SEOUL_OPEN_DATA_API_KEY='',
            SEOUL_OPEN_API_BASE_URL='http://openapi.seoul.go.kr:8088'))
        self.settings.start()
        self.addCleanup(self.settings.stop)
        self.addCleanup(service._cache.clear)

    def test_zero_is_not_missing_and_bad_coordinates_are_discarded(self):
        self.assertEqual(service._normalize(bike(), 'bike').bikes_available, 0)
        self.assertIsNone(service._normalize(bike(available=''), 'bike').bikes_available)
        self.assertIsNone(service._normalize(bike(available='-1'), 'bike').bikes_available)
        self.assertIsNone(service._normalize(bike(lat='NaN'), 'bike'))
        self.assertIsNone(service._normalize(bike(lat='0'), 'bike'))

    @patch.object(service, '_fetch_page')
    def test_pagination_does_not_drop_stations_after_first_thousand(self, fetch):
        fetch.side_effect = [[bike('ST-west', lat='37.4')] * 1000, [bike('ST-east', available='7')]]
        result = service.list_transit('bike', 37.49, 127.09, 37.51, 127.11)
        self.assertEqual(fetch.call_count, 2)
        self.assertEqual(fetch.call_args.args[2:], (1001, 2000))
        self.assertEqual(result.total, 1)
        self.assertEqual(result.items[0].bikes_available, 7)
        self.assertEqual(result.items[0].id, 'bike-ST-east')

    @patch.object(service, '_fetch_page')
    def test_bounds_filter_and_nearest_first_limit(self, fetch):
        fetch.return_value = [bike('ST-far', lat='37.59'), bike('ST-near', lat='37.55'), bike('ST-out', lat='37.7')]
        result = service.list_transit('bike', 37.5, 127.0, 37.6, 127.2, limit=1)
        self.assertEqual(result.total, 2)
        self.assertEqual(result.items[0].id, 'bike-ST-near')
        for bounds in [(37.6, 127, 37.5, 127.2), (float('nan'), 127, 37.5, 127.2)]:
            with self.assertRaises(HTTPException):
                service.list_transit('bike', *bounds)

    @patch.object(service, '_fetch_page')
    def test_cached_inventory_retains_fetch_time_and_expires(self, fetch):
        fetch.return_value = [bike(available='3')]
        first = service._all_stops('bike')
        second = service._all_stops('bike')
        self.assertEqual(first, second)
        self.assertEqual(fetch.call_count, 1)
        _, observed, stops = service._cache['bike']
        service._cache['bike'] = (time.monotonic() - 61, observed, stops)
        fetch.return_value = [bike(available='0')]
        refreshed = service._all_stops('bike')
        self.assertEqual(fetch.call_count, 2)
        self.assertEqual(refreshed[1][0].bikes_available, 0)

    @patch.object(service, '_fetch_page', side_effect=HTTPException(503, 'Unavailable'))
    def test_failed_refresh_does_not_serve_stale_availability(self, fetch):
        service._cache['bike'] = (time.monotonic() - 90, datetime.now(timezone.utc), [service._normalize(bike(available='8'), 'bike')])
        with self.assertRaises(HTTPException):
            service._all_stops('bike')

    @patch.object(service, '_fetch_page')
    def test_subway_line_and_coordinates_match_provider(self, fetch):
        fetch.return_value = [{'BLDN_ID': '0150', 'BLDN_NM': '서울역', 'ROUTE': '1호선', 'LAT': '37.556228', 'LOT': '126.972135'}]
        result = service.list_transit('subway', 37.5, 126.9, 37.6, 127)
        self.assertEqual(result.items[0].line, '1호선')
        self.assertEqual(result.items[0].lng, 126.972135)
        self.assertIsNone(result.items[0].bikes_available)

    @patch.object(service, 'urlopen', side_effect=OSError('provider URL contains secret-value'))
    def test_upstream_error_does_not_expose_key(self, _fetch):
        with self.assertRaises(HTTPException) as caught:
            service._fetch_page('bikeList', 'secret-value', 1, 1000)
        self.assertNotIn('secret-value', caught.exception.detail)


if __name__ == '__main__':
    unittest.main()
