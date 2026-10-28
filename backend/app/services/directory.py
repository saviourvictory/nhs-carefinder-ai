import logging
import re

import httpx

from app.config import settings
from app.schemas import Provider
from app.services.geo import rank_by_distance
logger = logging.getLogger(__name__)


DEMO_PROVIDERS = [
        Provider(
        name="Demo GP Surgery A (Fictional)",
        service="GP surgery",
        address="Example Road, Colchester",
        postcode="CO1 1AA",
        phone=None,
        distance_miles=0.4,
        source="Synthetic demo fixture",
        demo=True,
    ),
    Provider(
        name="Demo GP Surgery B (Fictional)",
        service="GP surgery",
        address="Sample Street, Colchester",
        postcode="CO1 2BB",
        phone=None,
        distance_miles=0.8,
        source="Synthetic demo fixture",
        demo=True,
    ),
    Provider(
        name="Demo Community Health Centre",
        service="physiotherapy",
        address="Example Road, Colchester",
        postcode="CO1 1AA",
        phone="01234 567890",
        distance_miles=1.2,
        source="Synthetic demo fixture",
        demo=True,
    ),
    Provider(
        name="Demo NHS Outpatient Clinic",
        service="physiotherapy",
        address="Sample Street, Colchester",
        postcode="CO2 7AA",
        phone="01234 567891",
        distance_miles=3.4,
        source="Synthetic demo fixture",
        demo=True,
    ),
]


def _provider(row: dict, service: str) -> Provider:
    contacts = row.get("Contacts") or []

    phone = next(
        (
            contact.get("Value")
            for contact in contacts
            if contact.get("ContactType") == "Telephone"
        ),
        None,
    )

    website = next(
        (
            contact.get("Value")
            for contact in contacts
            if contact.get("ContactType") in ("URL", "Website")
        ),
        None,
    )

    address_parts = [
        row.get(field)
        for field in (
            "Address1",
            "Address2",
            "Address3",
            "City",
            "County",
            "Postcode",
        )
    ]

    return Provider(
        name=row.get("OrganisationName") or "Unnamed NHS organisation",
        organisation_code=row.get("ODSCode"),
        service=service,
        address=", ".join(part for part in address_parts if part),
        postcode=row.get("Postcode"),
        phone=phone,
        website=website,
        distance_miles=None,
        source="NHS Directory of Healthcare Services",
        demo=False,
    )


def _is_gp_search(service: str) -> bool:
    query = service.strip().lower()
    return any(
        term in query
        for term in (
            "gp",
            "general practitioner",
            "doctor",
            "family doctor",
            "surgery",
        )
    )


def _postcode_district(postcode: str) -> str:
    normalised = re.sub(r"\s+", "", postcode).upper()

    # Accept standard UK postcode formats, with or without an inward space.
    if not re.fullmatch(r"[A-Z]{1,2}\d[A-Z\d]?\d[A-Z]{2}", normalised):
        raise ValueError("Enter a valid UK postcode")

    # Remove the final three characters to obtain the postcode district.
    return normalised[:-3]



async def search_directory(
    service: str,
    postcode: str,
    limit: int,
    radius_miles: float = 10,
) -> list[Provider]:
    if settings.demo_mode or not settings.nhs_api_key:
        query = service.strip().lower()

        if _is_gp_search(query):
            matching = [
                provider
                for provider in DEMO_PROVIDERS
                if _is_gp_search(provider.service)
            ]
        else:
            matching = [
                provider
                for provider in DEMO_PROVIDERS
                if query in provider.service.lower()
                or provider.service.lower() in query
            ]

        matching = [
            provider
            for provider in matching
            if provider.distance_miles <= radius_miles
        ]
        return matching[:limit]

    is_gp = _is_gp_search(service)
    params = {
        "api-version": "3",
        "search": _postcode_district(postcode) if is_gp else service,
        "searchMode": "all",
        "searchFields": (
            "Postcode"
            if is_gp
            else "OrganisationName,Address1,Address2,Address3,City,County"
        ),
        "$top": str(limit),
        "$count": "false",
        "$select": (
            "ODSCode,OrganisationName,Contacts,Address1,Address2,"
            "Address3,City,County,Postcode,OrganisationTypeId"
        ),
    }

    if is_gp:
        params["$filter"] = "OrganisationTypeId eq 'GPB'"

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(8.0, connect=3.0)
    ) as client:
        response = await client.get(
            settings.nhs_api_base,
            params=params,
            headers={"apikey": settings.nhs_api_key},
        )

    try:
        logger.info("NHS directory upstream status: %s", response.status_code)  
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.error(
            "NHS directory API returned HTTP status %s",
            exc.response.status_code,
        )
        raise

    data = response.json()
    rows = data.get("value", [])

    if is_gp:
        requested_district = _postcode_district(postcode)
        filtered_rows = []

        for row in rows:
            candidate_postcode = row.get("Postcode") or ""
            try:
                candidate_district = _postcode_district(candidate_postcode)
            except ValueError:
                continue

            if candidate_district == requested_district:
                filtered_rows.append(row)

        rows = filtered_rows

    providers = [_provider(row, service) for row in rows]
    return await rank_by_distance(providers, postcode, radius_miles)
