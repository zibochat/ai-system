import os
import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("OPENAI_API_KEY", "test-key")

from api import app

client = TestClient(app)


def test_root_health():
    r = client.get("/")
    assert r.status_code == 200
    data = r.json()
    assert data.get("status") == "healthy"


def test_profile_default():
    r = client.get("/api/v1/profile/test_user")
    assert r.status_code == 200
    data = r.json()
    assert data.get("user_id") == "test_user"


def test_chat_and_history(monkeypatch):
    # Stub recommend to avoid external calls
    import recommender as R

    def fake_recommend(profile, user_message, max_count=5, user_id=None):
        return ("پاسخ تست", {"recommended_products": [], "intent": "conversation", "priority_used": None})

    monkeypatch.setattr(R, "recommend", fake_recommend)

    payload = {"user_id": "u1", "chat_id": "c1", "message": "سلام"}
    r = client.post("/api/v1/chat", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data.get("user_id") == "u1"
    assert data.get("chat_id") == "c1"
    assert "پاسخ" in data.get("response", "")

    r2 = client.get("/api/v1/conversation/u1", params={"chat_id": "c1"})
    assert r2.status_code == 200
    hist = r2.json()
    assert hist.get("user_id") == "u1"
    assert hist.get("chat_id") == "c1"
    assert hist.get("total_count", 0) >= 2


