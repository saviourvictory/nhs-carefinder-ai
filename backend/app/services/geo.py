"""Postcode geocoding and approximate straight-line distance calculations."""

from math import asin, cos, radians, sin, sqrt

import httpx

from app.schemas import Provider

POSTCODES_IO_URL = "https://api.postcodes.io/postcodes"


def haversine_miles(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """Calculate great-circle distance between two coordinates in miles."""
    radius_miles = 3958.7613
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = (
        sin(dlat / 2) ** 2
        + cos(radians(lat1))
        * cos(radians(lat2))
        * sin(dlon / 2) ** 2
    )
    return 2 * radius_miles * asin(sqrt(min(1.0, a)))


async def geocode_postcodes(
    postcodes: list[str],
) -> dict[str, tuple[float, float]]:
    """Resolve UK postcodes to latitude and longitude."""
    cleaned = list(dict.fromkeys(
        postcode.strip().upper()
        for postcode in postcodes
        if postcode and postcode.strip()
    ))
    if not cleaned:
        return {}

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(8.0, connect=3.0)
        ) as client:
            response = await client.post(
                POSTCODES_IO_URL,
                json={"postcodes": cleaned},
            )
            response.raise_for_status()
            records = response.json().get("result", [])
    except (httpx.HTTPError, ValueError):
        return {}

    coordinates = {}
    for record in records:
        result = record.get("result")
        if not result:
            continue

        latitude = result.get("latitude")
        longitude = result.get("longitude")
        query = record.get("query")

        if (
            query
            and isinstance(latitude, (int, float))
            and isinstance(longitude, (int, float))
        ):
            coordinates[query.strip().upper()] = (
                float(latitude),
                float(longitude),
            )

    return coordinates


async def rank_by_distance(
    providers: list[Provider],
    origin_postcode: str,
    radius_miles: float,
) -> list[Provider]:
    """Calculate distances, filter by radius, and sort nearest first."""
    postcodes = [origin_postcode]
    postcodes.extend(
        provider.postcode
        for provider in providers
        if provider.postcode
    )
    coordinates = await geocode_postcodes(postcodes)
    origin = coordinates.get(origin_postcode.strip().upper())

    if origin is None:
        # Without the user's coordinates, do not claim results are nearby.
        return providers

    ranked = []
    for provider in providers:
        destination = (
            coordinates.get(provider.postcode.strip().upper())
            if provider.postcode
            else None
        )

        if destination is None:
            ranked.append(provider.model_copy(
                update={"distance_miles": None}
            ))
            continue

        distance = haversine_miles(
            origin[0], origin[1], destination[0], destination[1]
        )

        if distance <= radius_miles:
            ranked.append(provider.model_copy(
                update={"distance_miles": round(distance, 2)}
            ))

    ranked.sort(
        key=lambda provider: (
            provider.distance_miles is None,
            provider.distance_miles
            if provider.distance_miles is not None
            else float("inf"),
        )
    )
    return ranked
