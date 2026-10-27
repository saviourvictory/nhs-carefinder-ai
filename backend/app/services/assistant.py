import httpx

from app.config import settings
from app.services.nhs_sources import retrieve_nhs_pages

NOTICE = (
    "Important: I can explain general NHS services and care pathways, but I cannot diagnose a condition, "
    "recommend surgery or treatment, or confirm appointment availability. For a life-threatening emergency, "
    "call 999. For urgent medical advice in England, contact NHS 111."
)


SYSTEM_PROMPT = """You are a cautious NHS care-navigation assistant for general information only.

PURPOSE
Explain NHS services and care pathways in clear, practical, plain English.

ACCURACY
- Never invent services, contact details, URLs, eligibility rules, waiting times, or citations.
- You do not have a verified NHS knowledge base or live appointment information.
- Never claim that you checked an official source unless you actually retrieved and checked it.
- If uncertain, say so and direct the user to the official NHS website.
- NHS pathways differ across England, Scotland, Wales, and Northern Ireland.

CARE NAVIGATION
- If a GP has no appointments, suggest contacting the practice to discuss options and urgency, and checking its online services.
- In England, NHS 111 can provide urgent medical advice when the user cannot get help from their GP.
- Pharmacists can advise on some minor illnesses, but not every condition is suitable for pharmacy care.
- Mention urgent treatment centres or minor injury units only when relevant; do not assume local availability.
- Do not suggest that a friend or family member can generally book appointments at their own GP practice for the user.
- Never claim to book appointments or check live availability.

SAFETY
- Never diagnose, recommend a specific treatment or surgery, or tell users their symptoms are safe.
- For a possible life-threatening emergency, tell the user to call 999 immediately.
- In England, NHS 111 is for urgent medical advice when it is not a life-threatening emergency.
- Prioritise urgent medical help when a user describes potentially serious symptoms.

PRIVACY
- Do not request names, NHS numbers, exact addresses, or unnecessary identifying information.


FORMATTING
- Answer in 3–6 short sentences unless numbered steps are genuinely useful.
- Use only facts supported by the retrieved NHS source content or the safety rules above.
- Do not add lists of medical conditions, eligibility rules, opening hours, or service features unless the retrieved source explicitly supports them.
- If the retrieved content does not answer the question, say so and direct the user to the official NHS website.
- For questions about NHS 111 versus 999, clearly explain: NHS 111 is for urgent medical help when it is not a life-threatening emergency; call 999 for a life-threatening emergency.
- Use plain text or simple Markdown. Avoid elaborate headings and long bullet lists.
- Never create Markdown links unless the exact URL appears in the retrieved source content.
- Do not output escaped Markdown, malformed links, or invented citations.
- Be calm, respectful, and concise.


Do not claim to be an official NHS service or a substitute for a qualified healthcare professional."""

def _fallback(message: str = "") -> dict:
    extra = f" {message}" if message else ""
    return {
        "answer": (
            "The local AI assistant is not available right now. Please try again shortly, or use the official "
            "NHS website for general information. For urgent medical advice in England, contact NHS 111; "
            "for a life-threatening emergency, call 999."
            + extra
            + "\n\n"
            + NOTICE
        ),
        "sources": [],
        "mode": "safe-fallback",
    }

async def chat(question: str) -> dict:
    """Ask a locally hosted Ollama model. No question is persisted by this service."""
    if not settings.ollama_url or not settings.ollama_model:
        return _fallback("The Ollama URL or model is not configured.")
    import re

    emergency_question = re.search(
        r"\b(111|999)\b", question
    ) and re.search(
        r"\b(versus|instead of|rather than|or|when should|difference)\b",
        question.lower(),
    )
    gp_availability_question = re.search(
        r"\b(gp|doctor|surgery)\b", question.lower()
    ) and re.search(
        r"\b(no appointments|no appointment|fully booked|can't get an appointment|cannot get an appointment)\b",
        question.lower(),
    )

    if gp_availability_question:
        return {
            "answer": (
                "If your GP has no appointments available, contact your GP practice "
                "to explain your needs and ask what options are available. Check your "
                "practice's website or online services for appointment information. "
                "If you need urgent medical advice in England, contact NHS 111. "
                "For a life-threatening emergency, call 999.\n\n"
                + NOTICE
            ),
            "sources": [
                {
                    "title": source["title"],
                    "url": source["url"],
                }
                for source in await retrieve_nhs_pages(question)
            ],
            "mode": "rule-based-care-navigation",
        }

    chest_pain_question = re.search(
        r"\b(chest pain|pain in my chest|chest hurts|chest discomfort)\b",
        question.lower(),
    )

    if chest_pain_question:
        return {
            "answer": (
                "Chest pain can be serious. Call 999 immediately if you are "
                "experiencing chest pain. Do not drive yourself to A&E.\n\n"
                + NOTICE
            ),
            "sources": [],
            "mode": "rule-based-safety",
        }
    if emergency_question:
        return {
            "answer": (
                "In England, use NHS 111 for urgent medical advice when "
                "it is not a life-threatening emergency. Call 999 for a "
                "life-threatening emergency. If you think someone's life "
                "is in immediate danger, call 999.\n\n"
                + NOTICE
            ),
            "sources": [
                {
                    "title": source["title"],
                    "url": source["url"],
                }
                for source in await retrieve_nhs_pages(question)
            ],
            "mode": "rule-based-safety",
        }

    url = settings.ollama_url.rstrip("/") + "/api/chat"
    sources = await retrieve_nhs_pages(question)

    source_context = "\n\n".join(
        f"Source: {source['title']}\n"
        f"URL: {source['url']}\n"
        f"Content: {source['text']}"
        for source in sources
    )

    if source_context:
        source_instruction = (
            "\n\nTreat the retrieved NHS source content as the only source "
            "of factual NHS service information. Do not add advice based on "
            "general assumptions. Do not invent opening hours, availability, "
            "eligibility, referrals, temporary GP options, or service features. "
            "If a detail is not explicitly supported by the retrieved content, "
            "omit it. Answer in 3-5 short sentences. If the sources do not "
            "answer the question, say so and direct the user to the official "
            "NHS website. Only cite URLs included in the retrieved sources.\n\n"
            + source_context
        )
    else:
        source_instruction = (
            "\n\nNo NHS source pages could be retrieved. Do not claim the answer "
            "is verified NHS guidance or invent citations."
        )
    payload = {
        "model": settings.ollama_model,
        "stream": False,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT + source_instruction},
            {"role": "user", "content": question},
        ],
        "options": {"temperature": 0.1, "num_predict": 220},
    }
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=5.0)) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
        answer = data.get("message", {}).get("content", "").strip()
                # Avoid presenting unverified GP registration fees as fact.
        if re.search(r"£\s*\d+\s*[-–]\s*£?\s*\d+", answer):
            answer = (
                "I cannot verify a GP registration fee from the available "
                "sources. Please check the official NHS website for current "
                "registration guidance."
            )
        import re
        answer = re.sub(r"\\+(\*+)", r"\1", answer)
        answer = re.sub(r"\\+([.!])", r"\1", answer)
        if not answer:
            return _fallback("The model returned an empty response.")
        return {
            "answer": answer + "\n\n" + NOTICE,
            "sources": [
                {"title": source["title"], "url": source["url"]}
                for source in sources
            ],
            "mode": "ollama-local",
        }
    except (httpx.ConnectError, httpx.TimeoutException):
        return _fallback(
            f"Start the Ollama service and download the configured model ({settings.ollama_model})."
        )
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        return _fallback("Check the Ollama service and model configuration.")
