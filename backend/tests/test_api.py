from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)

def test_health_and_security_headers():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.headers["x-content-type-options"] == "nosniff"


def test_search_demo_notice(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "demo_mode", True)

    r = client.post(
        "/api/search",
        json={"service": "physiotherapy", "postcode": "CO1 1AA"},
    )

    assert r.status_code == 200
    assert "Synthetic" in r.json()["notice"]
    assert all(item["demo"] for item in r.json()["results"])


def test_bad_payload_rejected():
    assert client.post("/api/search", json={"service":"x","postcode":"CO1"}).status_code == 422

def test_chat_does_not_diagnose():
    r = client.post("/api/chat", json={"question":"What is wrong with my knee?"})
    assert r.status_code == 200
    assert "cannot diagnose" in r.json()["answer"]


def test_chat_returns_safe_fallback_when_ollama_unavailable(monkeypatch):
    import asyncio

    import httpx
    from app.services import assistant

    async def fake_post(*args, **kwargs):
        raise httpx.ConnectError("not running")

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            return False
        async def post(self, *args, **kwargs):
            return await fake_post(*args, **kwargs)
        async def get(self, *args, **kwargs):
            raise httpx.ConnectError("NHS source unavailable")

    monkeypatch.setattr(assistant.httpx, "AsyncClient", FakeClient)
    result = asyncio.run(assistant.chat("How do I find a GP?"))
    assert result["mode"] == "safe-fallback"
    assert "NHS 111" in result["answer"]

def test_gp_no_appointments_uses_rule_based_response():
    r = client.post(
        "/api/chat",
        json={"question": "What can I do if my GP has no appointments available?"},
    )

    assert r.status_code == 200
    data = r.json()
    assert data["mode"] == "rule-based-care-navigation"
    assert "NHS 111" in data["answer"]
    assert "999" in data["answer"]


def test_nhs_111_vs_999_uses_safety_rule():
    r = client.post(
        "/api/chat",
        json={"question": "When should I use NHS 111 instead of calling 999?"},
    )

    assert r.status_code == 200
    data = r.json()
    assert data["mode"] == "rule-based-safety"
    assert "NHS 111" in data["answer"]
    assert "999" in data["answer"]


def test_chest_pain_triggers_emergency_safety_rule():
    r = client.post(
        "/api/chat",
        json={"question": "I have chest pain. What should I do?"},
    )

    assert r.status_code == 200
    data = r.json()
    assert data["mode"] == "rule-based-safety"
    assert "999" in data["answer"]
    assert "chest pain" in data["answer"].lower()


def test_gp_registration_response_avoids_unverified_claims():
    r = client.post(
        "/api/chat",
        json={"question": "How do I register with a GP in England?"},
    )

    assert r.status_code == 200
    data = r.json()
    answer = data["answer"].lower()

    assert "cannot diagnose" in answer
    assert "nhs.uk" in str(data["sources"]).lower()
    assert "£20-£30" not in answer

