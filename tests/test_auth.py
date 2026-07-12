import pytest

pytestmark = pytest.mark.asyncio


async def test_register_success(client):
    response = await client.post(
        "/auth/register",
        json={"email": "newuser@example.com", "password": "strongpass123", "full_name": "New User"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "newuser@example.com"
    assert body["full_name"] == "New User"
    assert "id" in body
    assert "password" not in body  # never leak the hash back to the client


async def test_register_duplicate_email_rejected(client, registered_user):
    email, password = registered_user
    response = await client.post(
        "/auth/register",
        json={"email": email, "password": "anotherpassword123"},
    )
    assert response.status_code == 409


async def test_register_short_password_rejected(client):
    response = await client.post(
        "/auth/register",
        json={"email": "shortpass@example.com", "password": "123"},
    )
    assert response.status_code == 422


async def test_login_success(client, registered_user):
    email, password = registered_user
    response = await client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert "refresh_token" in body
    assert body["token_type"] == "bearer"


async def test_login_wrong_password_rejected(client, registered_user):
    email, _ = registered_user
    response = await client.post("/auth/login", json={"email": email, "password": "wrongpassword"})
    assert response.status_code == 401


async def test_login_nonexistent_email_rejected(client):
    response = await client.post(
        "/auth/login", json={"email": "nobody@example.com", "password": "whatever123"}
    )
    assert response.status_code == 401


async def test_refresh_token_issues_new_access_token(client, registered_user):
    email, password = registered_user
    login_response = await client.post("/auth/login", json={"email": email, "password": password})
    refresh_token = login_response.json()["refresh_token"]

    response = await client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert response.status_code == 200
    assert "access_token" in response.json()


async def test_logout_revokes_refresh_token(client, registered_user):
    email, password = registered_user
    login_response = await client.post("/auth/login", json={"email": email, "password": password})
    refresh_token = login_response.json()["refresh_token"]

    logout_response = await client.post("/auth/logout", json={"refresh_token": refresh_token})
    assert logout_response.status_code == 204

    # Using the same refresh token again should now fail.
    reuse_response = await client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert reuse_response.status_code == 401


async def test_get_my_profile_requires_login(client):
    response = await client.get("/users/me")
    assert response.status_code == 401


async def test_get_my_profile_with_valid_token(client, auth_headers):
    response = await client.get("/users/me", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["email"] == "testuser@example.com"
