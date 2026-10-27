import asyncio

from app.schemas import Provider
from app.services import geo


def make_provider(name, postcode):
    return Provider(
        name=name,
        service="GP",
        address=f"Example Road, {postcode}",
        postcode=postcode,
        source="Test fixture",
        demo=False,
    )


def test_same_point_zero_distance():
    assert geo.haversine_miles(51.5, -0.1, 51.5, -0.1) == 0


def test_london_to_colchester_approx():
    distance = geo.haversine_miles(
        51.5074, -0.1278, 51.8892, 0.9042
    )
    assert 50 < distance < 60


def test_radius_filter_and_nearest_first(monkeypatch):
    providers = [
        make_provider("Far surgery", "CC3 3CC"),
        make_provider("Near surgery", "BB2 2BB"),
        make_provider("Middle surgery", "AA1 1AA"),
    ]

    coordinates = {
        "CO1 2ZT": (51.5, 0.0),
        "BB2 2BB": (51.501, 0.0),
        "AA1 1AA": (51.51, 0.0),
        "CC3 3CC": (52.5, 0.0),
    }

    async def fake_geocode(postcodes):
        return coordinates

    monkeypatch.setattr(geo, "geocode_postcodes", fake_geocode)

    results = asyncio.run(
        geo.rank_by_distance(providers, "CO1 2ZT", 2)
    )

    assert [p.name for p in results] == [
        "Near surgery",
        "Middle surgery",
    ]
    assert results[0].distance_miles < results[1].distance_miles
    assert all(p.distance_miles <= 2 for p in results)


def test_missing_origin_coordinates_preserves_results(monkeypatch):
    providers = [make_provider("Example surgery", "AA1 1AA")]

    async def fake_geocode(postcodes):
        return {}

    monkeypatch.setattr(geo, "geocode_postcodes", fake_geocode)

    results = asyncio.run(
        geo.rank_by_distance(providers, "CO1 2ZT", 1)
    )

    assert len(results) == 1
    assert results[0].distance_miles is None


def test_unknown_provider_distance_is_not_invented(monkeypatch):
    providers = [
        make_provider("Known surgery", "AA1 1AA"),
        make_provider("Unknown surgery", "ZZ1 1ZZ"),
    ]

    async def fake_geocode(postcodes):
        return {
            "CO1 2ZT": (51.5, 0.0),
            "AA1 1AA": (51.501, 0.0),
        }

    monkeypatch.setattr(geo, "geocode_postcodes", fake_geocode)

    results = asyncio.run(
        geo.rank_by_distance(providers, "CO1 2ZT", 2)
    )

    assert results[0].name == "Known surgery"
    assert results[0].distance_miles is not None
    assert results[1].name == "Unknown surgery"
    assert results[1].distance_miles is None
