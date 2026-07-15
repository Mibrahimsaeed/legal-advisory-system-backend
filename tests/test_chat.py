import pytest

pytestmark = pytest.mark.asyncio


async def test_send_message_requires_login(client):
    response = await client.post("/chat/some-id/message", json={"question": "What are my rights?"})
    assert response.status_code == 401


async def test_send_message_to_nonexistent_conversation_returns_404(client, auth_headers):
    response = await client.post(
        "/chat/does-not-exist/message",
        json={"question": "What are my rights?"},
        headers=auth_headers,
    )
    assert response.status_code == 404


async def test_send_message_success(client, auth_headers):
    create_response = await client.post(
        "/conversations", json={"title": "Chat test"}, headers=auth_headers
    )
    conversation_id = create_response.json()["id"]

    response = await client.post(
        f"/chat/{conversation_id}/message",
        json={"question": "What are my tenant rights in Pakistan?"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["role"] == "assistant"
    assert body["conversation_id"] == conversation_id
    assert len(body["content"]) > 0


async def test_send_message_saves_both_user_and_assistant_messages(client, auth_headers):
    create_response = await client.post(
        "/conversations", json={"title": "History test"}, headers=auth_headers
    )
    conversation_id = create_response.json()["id"]

    await client.post(
        f"/chat/{conversation_id}/message",
        json={"question": "First question"},
        headers=auth_headers,
    )

    messages_response = await client.get(
        f"/conversations/{conversation_id}/messages", headers=auth_headers
    )
    items = messages_response.json()["items"]
    roles = [m["role"] for m in items]
    assert "user" in roles
    assert "assistant" in roles
    assert len(items) == 2


async def test_send_message_with_empty_question_rejected(client, auth_headers):
    create_response = await client.post(
        "/conversations", json={"title": "Empty test"}, headers=auth_headers
    )
    conversation_id = create_response.json()["id"]

    response = await client.post(
        f"/chat/{conversation_id}/message", json={"question": ""}, headers=auth_headers
    )
    assert response.status_code == 422


async def test_user_cannot_chat_in_another_users_conversation(client, auth_headers):
    create_response = await client.post(
        "/conversations", json={"title": "Private chat"}, headers=auth_headers
    )
    conversation_id = create_response.json()["id"]

    await client.post(
        "/auth/register",
        json={"email": "chatintruder@example.com", "password": "intruderpass123"},
    )
    login_response = await client.post(
        "/auth/login", json={"email": "chatintruder@example.com", "password": "intruderpass123"}
    )
    other_headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}

    response = await client.post(
        f"/chat/{conversation_id}/message",
        json={"question": "Trying to intrude"},
        headers=other_headers,
    )
    assert response.status_code == 403


async def test_conversation_history_grows_with_each_message(client, auth_headers):
    create_response = await client.post(
        "/conversations", json={"title": "Growing history"}, headers=auth_headers
    )
    conversation_id = create_response.json()["id"]

    await client.post(
        f"/chat/{conversation_id}/message", json={"question": "Question one"}, headers=auth_headers
    )
    await client.post(
        f"/chat/{conversation_id}/message", json={"question": "Question two"}, headers=auth_headers
    )

    messages_response = await client.get(
        f"/conversations/{conversation_id}/messages", headers=auth_headers
    )
    assert messages_response.json()["total"] == 4  # 2 user + 2 assistant
