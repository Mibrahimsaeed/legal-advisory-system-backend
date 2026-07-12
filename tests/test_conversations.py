import pytest

pytestmark = pytest.mark.asyncio


async def test_create_conversation_requires_login(client):
    response = await client.post("/conversations", json={"title": "Test"})
    assert response.status_code == 401


async def test_create_conversation_success(client, auth_headers):
    response = await client.post(
        "/conversations", json={"title": "My legal question"}, headers=auth_headers
    )
    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "My legal question"
    assert "id" in body


async def test_create_conversation_default_title(client, auth_headers):
    response = await client.post("/conversations", json={}, headers=auth_headers)
    assert response.status_code == 201
    assert response.json()["title"] == "New Conversation"


async def test_list_conversations(client, auth_headers):
    await client.post("/conversations", json={"title": "First"}, headers=auth_headers)
    await client.post("/conversations", json={"title": "Second"}, headers=auth_headers)

    response = await client.get("/conversations", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 2
    assert len(body["items"]) >= 2


async def test_get_conversation_by_id(client, auth_headers):
    create_response = await client.post(
        "/conversations", json={"title": "Findable"}, headers=auth_headers
    )
    conversation_id = create_response.json()["id"]

    response = await client.get(f"/conversations/{conversation_id}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["id"] == conversation_id


async def test_get_nonexistent_conversation_returns_404(client, auth_headers):
    response = await client.get("/conversations/does-not-exist", headers=auth_headers)
    assert response.status_code == 404


async def test_delete_conversation(client, auth_headers):
    create_response = await client.post(
        "/conversations", json={"title": "To delete"}, headers=auth_headers
    )
    conversation_id = create_response.json()["id"]

    delete_response = await client.delete(f"/conversations/{conversation_id}", headers=auth_headers)
    assert delete_response.status_code == 204

    get_response = await client.get(f"/conversations/{conversation_id}", headers=auth_headers)
    assert get_response.status_code == 404


async def test_get_messages_for_empty_conversation(client, auth_headers):
    create_response = await client.post(
        "/conversations", json={"title": "Empty"}, headers=auth_headers
    )
    conversation_id = create_response.json()["id"]

    response = await client.get(f"/conversations/{conversation_id}/messages", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["items"] == []


async def test_user_cannot_access_another_users_conversation(client, auth_headers):
    # Create a conversation as the default test user.
    create_response = await client.post(
        "/conversations", json={"title": "Private"}, headers=auth_headers
    )
    conversation_id = create_response.json()["id"]

    # Register + log in as a second, different user.
    await client.post(
        "/auth/register",
        json={"email": "otheruser@example.com", "password": "otherpassword123"},
    )
    login_response = await client.post(
        "/auth/login", json={"email": "otheruser@example.com", "password": "otherpassword123"}
    )
    other_token = login_response.json()["access_token"]
    other_headers = {"Authorization": f"Bearer {other_token}"}

    response = await client.get(f"/conversations/{conversation_id}", headers=other_headers)
    assert response.status_code == 403
