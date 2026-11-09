"""Small talk must work with no database and no LLM running."""
import os

os.environ.setdefault("EMBEDDING_PROVIDER", "mock")
os.environ.setdefault("LLM_PROVIDER", "mock")
os.environ.setdefault("DATABASE_URL", "postgresql://invalid/test")

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_latin_greeting_gets_latin_reply():
    data = client.post("/api/v1/chat", json={"message": "Sain bnu?"}).json()
    assert data["intent"] == "greeting"
    assert data["input_script"] == "latin"
    assert data["answer"].startswith("Sain baina uu!")
    assert data["answer_cyrillic"].startswith("Сайн байна уу!")
    assert data["sources"] == []


def test_cyrillic_greeting_gets_cyrillic_reply():
    data = client.post("/api/v1/chat", json={"message": "Сайн байна уу"}).json()
    assert data["intent"] == "greeting"
    assert data["answer"].startswith("Сайн байна уу!")


def test_road_question_without_db_returns_503_not_a_greeting():
    resp = client.post("/api/v1/chat", json={"message": "yavgan zamiin urgun hed ve"})
    assert resp.status_code == 503
