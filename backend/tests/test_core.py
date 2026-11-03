"""Offline tests: no network, no API key."""
from app.geo import haversine_m, walk_estimate
from app.models import Place
from app.places import parse_overpass
from app.planner import assemble_days


def test_haversine_colosseum_to_pantheon():
    # Real distance is ~1.9 km straight line
    d = haversine_m(41.8902, 12.4922, 41.8986, 12.4769)
    assert 1500 < d < 2200


def test_walk_estimate_has_detour():
    meters, minutes = walk_estimate(41.8902, 12.4922, 41.8986, 12.4769)
    assert meters > haversine_m(41.8902, 12.4922, 41.8986, 12.4769)
    assert minutes >= 20


def test_parse_overpass_dedup_and_center():
    elements = [
        {"type": "node", "id": 1, "lat": 1.0, "lon": 2.0,
         "tags": {"name": "Colosseo", "name:en": "Colosseum", "tourism": "attraction"}},
        {"type": "way", "id": 2, "center": {"lat": 1.0, "lon": 2.0},
         "tags": {"name": "Colosseo", "tourism": "attraction"}},  # duplicate
        {"type": "node", "id": 3, "lat": 1.1, "lon": 2.1,
         "tags": {"name": "Trattoria", "amenity": "restaurant", "cuisine": "italian"}},
    ]
    places = parse_overpass(elements)
    assert [p.name for p in places] == ["Colosseum", "Trattoria"]
    assert places[1].category == "restaurant"


def test_assemble_drops_hallucinated_and_duplicate_ids():
    a = Place(id="node/1", name="A", category="sight", lat=41.89, lon=12.49)
    b = Place(id="node/2", name="B", category="cafe", lat=41.90, lon=12.48)
    raw = [
        {"day": 1, "title": "D1", "stops": [
            {"id": "node/1", "note": "x"},
            {"id": "node/999", "note": "invented"},
            {"id": "node/2", "note": "y"},
        ]},
        {"day": 2, "title": "D2", "stops": [{"id": "node/1", "note": "repeat"}]},
    ]
    days = assemble_days(raw, [a, b])
    assert len(days) == 1  # day 2 had only a repeated place -> dropped
    assert [s.place.id for s in days[0].stops] == ["node/1", "node/2"]
    assert days[0].stops[1].walk_from_prev_m > 0
