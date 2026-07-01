"""Tests for semantic_wall/api/main.py using FastAPI's TestClient, with the
agent and check-in engine mocked — no live provider/Supabase calls."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from semantic_wall import config
from semantic_wall.api.main import app
from semantic_wall.checkin import engine as checkin_engine


@pytest.fixture
def client():
    checkin_engine.reset_sessions_for_tests()
    return TestClient(app)


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "semantic-wall"
    assert "memory_configured" in body
    assert "providers" in body


def test_health_endpoint_not_gated_by_api_secret(client, monkeypatch):
    # /health should stay reachable for monitoring even when the secret is set.
    monkeypatch.setattr(config.settings, "api_shared_secret", "top-secret")
    response = client.get("/health")
    assert response.status_code == 200


def test_chat_endpoint_rejects_missing_secret_when_configured(client, monkeypatch):
    monkeypatch.setattr(config.settings, "api_shared_secret", "top-secret")
    response = client.post("/api/chat", json={"user_id": "u1", "session_id": "s1", "query": "hello"})
    assert response.status_code == 401


def test_chat_endpoint_rejects_wrong_secret_when_configured(client, monkeypatch):
    monkeypatch.setattr(config.settings, "api_shared_secret", "top-secret")
    response = client.post(
        "/api/chat",
        json={"user_id": "u1", "session_id": "s1", "query": "hello"},
        headers={"X-Api-Secret": "wrong-secret"},
    )
    assert response.status_code == 401


def test_chat_endpoint_accepts_correct_secret_when_configured(client, monkeypatch):
    monkeypatch.setattr(config.settings, "api_shared_secret", "top-secret")
    fake_result = {
        "response": "hi",
        "agent_id": "strategist",
        "memories_used": 0,
        "model": "anthropic:claude-sonnet-5",
    }
    with patch("semantic_wall.api.main.SemanticWallAgent") as mock_agent_cls:
        mock_agent_cls.return_value.chat.return_value = fake_result
        response = client.post(
            "/api/chat",
            json={"user_id": "u1", "session_id": "s1", "query": "hello"},
            headers={"X-Api-Secret": "top-secret"},
        )
    assert response.status_code == 200


def test_chat_endpoint_returns_agent_response(client):
    fake_result = {
        "response": "hi from the strategist",
        "agent_id": "strategist",
        "memories_used": 2,
        "model": "anthropic:claude-sonnet-5",
    }
    with patch("semantic_wall.api.main.SemanticWallAgent") as mock_agent_cls:
        mock_agent_cls.return_value.chat.return_value = fake_result
        response = client.post(
            "/api/chat",
            json={"user_id": "u1", "session_id": "s1", "query": "hello"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["response"] == "hi from the strategist"
    assert body["memories_used"] == 2
    assert body["checkin_due"] is False


def test_chat_endpoint_reports_checkin_due(client):
    fake_result = {
        "response": "answer",
        "agent_id": "strategist",
        "memories_used": 0,
        "model": "none:none",
    }
    with patch("semantic_wall.api.main.SemanticWallAgent") as mock_agent_cls, \
         patch.object(checkin_engine, "is_checkin_due", return_value=True):
        mock_agent_cls.return_value.chat.return_value = fake_result
        response = client.post(
            "/api/chat",
            json={"user_id": "u1", "session_id": "s1", "query": "hello"},
        )

    assert response.json()["checkin_due"] is True


def test_chat_endpoint_500_on_unexpected_error(client):
    with patch("semantic_wall.api.main.SemanticWallAgent") as mock_agent_cls:
        mock_agent_cls.return_value.chat.side_effect = RuntimeError("boom")
        response = client.post(
            "/api/chat",
            json={"user_id": "u1", "session_id": "s1", "query": "hello"},
        )
    assert response.status_code == 500


def test_checkin_status_not_due(client):
    response = client.get("/api/checkin/status", params={"session_id": "unknown"})
    assert response.status_code == 200
    assert response.json() == {"due": False, "questions": []}


def test_checkin_status_due_includes_questions(client):
    with patch.object(checkin_engine, "is_checkin_due", return_value=True):
        response = client.get("/api/checkin/status", params={"session_id": "s1"})
    body = response.json()
    assert body["due"] is True
    assert len(body["questions"]) == 5


def test_submit_checkin_success(client):
    with patch.object(checkin_engine, "submit_checkin", return_value={"recorded": True, "memory_rows_updated": 0}):
        response = client.post(
            "/api/checkin",
            json={
                "user_id": "u1",
                "session_id": "s1",
                "completion_confirmation": True,
                "quality_rating": 5,
                "improvement_note": "worked great honestly",
                "used_in_real_work": True,
                "willingness_to_pay": "yes",
            },
        )
    assert response.status_code == 200
    assert response.json() == {"recorded": True, "memory_rows_updated": 0}


def test_submit_checkin_out_of_range_rating_rejected_by_pydantic(client):
    response = client.post(
        "/api/checkin",
        json={
            "user_id": "u1",
            "session_id": "s1",
            "completion_confirmation": True,
            "quality_rating": 9,
            "improvement_note": "worked great honestly",
            "used_in_real_work": True,
            "willingness_to_pay": "yes",
        },
    )
    assert response.status_code == 422


def test_submit_checkin_engine_validation_error_returns_422(client):
    with patch.object(
        checkin_engine, "submit_checkin", side_effect=checkin_engine.CheckinValidationError("bad note")
    ):
        response = client.post(
            "/api/checkin",
            json={
                "user_id": "u1",
                "session_id": "s1",
                "completion_confirmation": True,
                "quality_rating": 3,
                "improvement_note": "worked great honestly",
                "used_in_real_work": True,
                "willingness_to_pay": "yes",
            },
        )
    assert response.status_code == 422


def test_submit_checkin_unexpected_error_returns_500(client):
    with patch.object(checkin_engine, "submit_checkin", side_effect=RuntimeError("supabase down")):
        response = client.post(
            "/api/checkin",
            json={
                "user_id": "u1",
                "session_id": "s1",
                "completion_confirmation": True,
                "quality_rating": 3,
                "improvement_note": "worked great honestly",
                "used_in_real_work": True,
                "willingness_to_pay": "yes",
            },
        )
    assert response.status_code == 500
    assert "supabase down" not in response.text
