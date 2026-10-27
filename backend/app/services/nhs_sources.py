
"""Retrieve relevant information from a small set of official NHS pages."""

import re
from html import unescape

import httpx

NHS_PAGES = {
    "GP appointments": "https://www.nhs.uk/nhs-services/gps/gp-appointments-and-bookings/",
    "NHS 111": "https://www.nhs.uk/nhs-services/urgent-and-emergency-care-services/when-to-use-111/",
    "Urgent and emergency care": "https://www.nhs.uk/nhs-services/urgent-and-emergency-care-services/",
    "Pharmacy services": "https://www.nhs.uk/nhs-services/pharmacies/",
}



def _extract_text(html: str) -> str:
    """Remove common HTML elements and return readable page text."""
    html = re.sub(
        r"<(script|style|nav|header|footer|noscript)\b[^>]*>.*?</\1>",
        " ",
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    html = re.sub(r"<[^>]+>", " ", html)
    text = unescape(html)
    return re.sub(r"\s+", " ", text).strip()


async def retrieve_nhs_pages(question: str) -> list[dict]:
    """Fetch official NHS pages and return text from pages that can be reached."""
    question_words = {
        word.lower()
        for word in re.findall(r"[a-zA-Z]{3,}", question)
    }

    keywords = {
        "GP appointments": {"gp", "doctor", "appointment", "practice", "booking"},
        "NHS 111": {"111", "urgent", "advice", "help", "emergency"},
        "Urgent and emergency care": {"urgent", "emergency", "centre", "center", "walk"},
        "Pharmacy services": {"pharmacy", "pharmacist", "medicine", "minor", "illness"},
    }

    selected = [
        (title, url)
        for title, url in NHS_PAGES.items()
        if question_words.intersection(keywords[title])
    ]

    if not selected:
        selected = list(NHS_PAGES.items())[:2]

    results = []

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(10.0, connect=4.0),
        follow_redirects=True,
        headers={"User-Agent": "NHS-CareNavigation-Portfolio-Prototype/0.1"},
    ) as client:
        for title, url in selected[:3]:
            try:
                response = await client.get(url)
                response.raise_for_status()

                if "text/html" not in response.headers.get("content-type", ""):
                    continue

                text = _extract_text(response.text)
                if text:
                    results.append(
                        {
                            "title": title,
                            "url": str(response.url),
                            "text": text[:5000],
                        }
                    )
            except httpx.HTTPError:
                # A page that cannot be retrieved is not treated as a source.
                continue

    return results

