from unittest.mock import patch

from app.api.v1.local import service


def test_recommend_place_prefers_lower_congestion_over_nearest_crowded_spot():
    spots = [
        {"name": "가까운 혼잡역", "lat": 37.5003, "lng": 127.0003},
        {"name": "조금 먼 공원", "lat": 37.5030, "lng": 127.0030},
    ]

    with (
        patch.object(service, "SPOTS", spots),
        patch.object(service, "_fetch_congestion", side_effect=[("붐빔", "많이 붐벼요"), ("여유", "한산해요")]),
    ):
        response = service.recommend_place(lat=37.5, lng=127.0, hour=19)

    assert [item.name for item in response.results] == ["조금 먼 공원", "가까운 혼잡역"]
    assert response.results[0].congestionLevel == "여유"
    assert response.results[0].recommendationScore > response.results[1].recommendationScore
