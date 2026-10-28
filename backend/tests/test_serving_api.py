from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_roles_lists_access_policy_roles():
    response = client.get("/roles")
    assert response.status_code == 200
    assert response.json() == {"roles": ["executive", "admin", "analyst", "support", "marketing"]}


def test_cors_header_present_for_allowed_origin():
    response = client.get("/health", headers={"Origin": "http://localhost:5173"})
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_cors_header_absent_for_disallowed_origin():
    response = client.get("/health", headers={"Origin": "http://evil.example"})
    assert "access-control-allow-origin" not in response.headers


def test_query_unknown_role_returns_400_with_detail():
    response = client.post("/query", json={"query": "hi", "role": "ghost"})
    assert response.status_code == 400
    assert "ghost" in response.json()["detail"]
