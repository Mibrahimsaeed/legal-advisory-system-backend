"""Forgot password (email code) and password-protected account deletion."""

import re

import pytest

from app.auth import service as auth_service

pytestmark = pytest.mark.asyncio

EMAIL = "reset.user@example.com"
PASSWORD = "originalpass123"


@pytest.fixture
def outbox(monkeypatch):
    """Capture emails instead of sending them."""
    sent = []

    async def fake_send_email(to, subject, body):
        sent.append({"to": to, "subject": subject, "body": body})

    monkeypatch.setattr(auth_service, "send_email", fake_send_email)
    return sent


def _code(mail) -> str:
    return re.search(r"\b(\d{6})\b", mail["body"]).group(1)


async def _register(client, email=EMAIL, password=PASSWORD):
    await client.post("/auth/register", json={"email": email, "password": password})


async def test_forgot_password_sends_code_and_reset_works(client, outbox):
    await _register(client)
    r = await client.post("/auth/forgot-password", json={"email": EMAIL})
    assert r.status_code == 200
    assert len(outbox) == 1 and outbox[0]["to"] == EMAIL
    code = _code(outbox[0])

    r = await client.post(
        "/auth/reset-password", json={"email": EMAIL, "code": code, "new_password": "brandnewpass1"}
    )
    assert r.status_code == 200

    old = await client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert old.status_code == 401
    new = await client.post("/auth/login", json={"email": EMAIL, "password": "brandnewpass1"})
    assert new.status_code == 200


async def test_code_cannot_be_reused(client, outbox):
    email = "reuse@example.com"
    await _register(client, email)
    await client.post("/auth/forgot-password", json={"email": email})
    code = _code(outbox[-1])
    body = {"email": email, "code": code, "new_password": "anotherpass1"}
    assert (await client.post("/auth/reset-password", json=body)).status_code == 200
    assert (await client.post("/auth/reset-password", json=body)).status_code == 400


async def test_unknown_email_gives_same_answer_and_sends_nothing(client, outbox):
    r = await client.post("/auth/forgot-password", json={"email": "nobody@example.com"})
    assert r.status_code == 200
    assert outbox == []


async def test_wrong_code_rejected_and_locks_after_five_attempts(client, outbox):
    email = "guesser@example.com"
    await _register(client, email)
    await client.post("/auth/forgot-password", json={"email": email})
    real = _code(outbox[-1])
    wrong = "000000" if real != "000000" else "111111"
    for _ in range(5):
        r = await client.post(
            "/auth/reset-password", json={"email": email, "code": wrong, "new_password": "whatever123"}
        )
        assert r.status_code == 400
    # After 5 wrong guesses even the real code no longer works.
    r = await client.post(
        "/auth/reset-password", json={"email": email, "code": real, "new_password": "whatever123"}
    )
    assert r.status_code == 400


async def test_resend_cooldown(client, outbox):
    email = "cooldown@example.com"
    await _register(client, email)
    await client.post("/auth/forgot-password", json={"email": email})
    await client.post("/auth/forgot-password", json={"email": email})
    assert len([m for m in outbox if m["to"] == email]) == 1


async def test_reset_rejects_short_password_and_bad_code_format(client):
    r = await client.post(
        "/auth/reset-password", json={"email": EMAIL, "code": "123456", "new_password": "short"}
    )
    assert r.status_code == 422
    r = await client.post(
        "/auth/reset-password", json={"email": EMAIL, "code": "12ab", "new_password": "longenough1"}
    )
    assert r.status_code == 422


async def _login_headers(client, email, password):
    r = await client.post("/auth/login", json={"email": email, "password": password})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def test_delete_account_requires_email_and_password(client):
    email = "deleter@example.com"
    await _register(client, email)
    headers = await _login_headers(client, email, PASSWORD)

    r = await client.request("DELETE", "/users/me", headers=headers, json={"email": email, "password": "wrongpass1"})
    assert r.status_code == 403
    r = await client.request("DELETE", "/users/me", headers=headers, json={"email": "other@example.com", "password": PASSWORD})
    assert r.status_code == 403
    r = await client.request("DELETE", "/users/me", headers=headers)
    assert r.status_code == 422

    r = await client.request("DELETE", "/users/me", headers=headers, json={"email": email, "password": PASSWORD})
    assert r.status_code == 204
    r = await client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 401
