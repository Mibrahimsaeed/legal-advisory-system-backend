import pytest

pytestmark = pytest.mark.asyncio


async def test_security_headers_present(client):
    """Every response should carry the protective headers added in Phase 6."""
    response = await client.get("/health")
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert "Permissions-Policy" in response.headers


async def test_health_check_returns_ok(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


async def test_invalid_json_body_returns_422_not_500(client):
    """Malformed input must produce a clean validation error, never a crash."""
    response = await client.post("/auth/register", json={"email": "not-an-email"})
    assert response.status_code == 422


async def test_unknown_route_returns_404(client):
    response = await client.get("/this-route-does-not-exist")
    assert response.status_code == 404


async def test_oversized_question_rejected(client, auth_headers):
    """Input length limits are enforced (max 4000 chars for chat questions)."""
    create_response = await client.post(
        "/conversations", json={"title": "Limit test"}, headers=auth_headers
    )
    conversation_id = create_response.json()["id"]

    huge_question = "x" * 5000
    response = await client.post(
        f"/chat/{conversation_id}/message",
        json={"question": huge_question},
        headers=auth_headers,
    )
    assert response.status_code == 422


async def test_wrong_token_type_rejected_for_protected_route(client, registered_user):
    """A refresh token must not be usable as an access token."""
    email, password = registered_user
    login_response = await client.post("/auth/login", json={"email": email, "password": password})
    refresh_token = login_response.json()["refresh_token"]

    response = await client.get(
        "/users/me", headers={"Authorization": f"Bearer {refresh_token}"}
    )
    assert response.status_code == 401


async def test_garbage_token_rejected(client):
    response = await client.get(
        "/users/me", headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert response.status_code == 401
