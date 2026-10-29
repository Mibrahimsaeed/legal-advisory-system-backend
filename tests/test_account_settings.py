"""Settings: change password and change email (verified by a code to the new address)."""

import re

import pytest

from app.users import service as users_service

pytestmark = pytest.mark.asyncio

PASSWORD = "settingspass123"


@pytest.fixture
def outbox(monkeypatch):
    sent = []

    async def fake_send_email(to, subject, body):
        sent.append({"to": to, "subject": subject, "body": body})

    monkeypatch.setattr(users_service, "send_email", fake_send_email)
    return sent


def _code(mail) -> str:
    return re.search(r"\b(\d{6})\b", mail["body"]).group(1)


async def _user(client, email):
    await client.post("/auth/register", json={"email": email, "password": PASSWORD, "full_name": "Settings User"})
    r = await client.post("/auth/login", json={"email": email, "password": PASSWORD})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def test_change_password(client):
    email = "chpw@example.com"
    h = await _user(client, email)
    r = await client.post("/users/me/change-password", headers=h, json={"current_password": "wrongpass1", "new_password": "newpass1234"})
    assert r.status_code == 403
    r = await client.post("/users/me/change-password", headers=h, json={"current_password": PASSWORD, "new_password": PASSWORD})
    assert r.status_code == 400
    r = await client.post("/users/me/change-password", headers=h, json={"current_password": PASSWORD, "new_password": "short"})
    assert r.status_code == 422
    r = await client.post("/users/me/change-password", headers=h, json={"current_password": PASSWORD, "new_password": "newpass1234"})
    assert r.status_code == 200
    assert (await client.post("/auth/login", json={"email": email, "password": PASSWORD})).status_code == 401
    assert (await client.post("/auth/login", json={"email": email, "password": "newpass1234"})).status_code == 200


async def test_change_email_full_flow(client, outbox):
    old, new = "old.addr@example.com", "new.addr@example.com"
    h = await _user(client, old)
    r = await client.post("/users/me/change-email", headers=h, json={"new_email": new, "password": PASSWORD})
    assert r.status_code == 200
    assert outbox[-1]["to"] == new  # code goes to the NEW address
    code = _code(outbox[-1])

    r = await client.post("/users/me/change-email/confirm", headers=h, json={"code": code})
    assert r.status_code == 200 and r.json()["email"] == new
    assert outbox[-1]["to"] == old  # old address is notified
    assert (await client.get("/users/me", headers=h)).json()["email"] == new
    assert (await client.post("/auth/login", json={"email": new, "password": PASSWORD})).status_code == 200
    assert (await client.post("/auth/login", json={"email": old, "password": PASSWORD})).status_code == 401


async def test_change_email_checks(client, outbox):
    h = await _user(client, "checks@example.com")
    await _user(client, "taken@example.com")
    r = await client.post("/users/me/change-email", headers=h, json={"new_email": "x@example.com", "password": "wrongpass1"})
    assert r.status_code == 403
    r = await client.post("/users/me/change-email", headers=h, json={"new_email": "taken@example.com", "password": PASSWORD})
    assert r.status_code == 409
    r = await client.post("/users/me/change-email", headers=h, json={"new_email": "checks@example.com", "password": PASSWORD})
    assert r.status_code == 400
    r = await client.post("/users/me/change-email", headers=h, json={"new_email": "not-an-email", "password": PASSWORD})
    assert r.status_code == 422


async def test_change_email_wrong_code_locks(client, outbox):
    h = await _user(client, "lock@example.com")
    await client.post("/users/me/change-email", headers=h, json={"new_email": "lock.new@example.com", "password": PASSWORD})
    real = _code(outbox[-1])
    wrong = "000000" if real != "000000" else "111111"
    for _ in range(5):
        assert (await client.post("/users/me/change-email/confirm", headers=h, json={"code": wrong})).status_code == 400
    assert (await client.post("/users/me/change-email/confirm", headers=h, json={"code": real})).status_code == 400


async def test_settings_need_login(client):
    assert (await client.post("/users/me/change-password", json={"current_password": "a", "new_password": "abcdefgh"})).status_code in (401, 403)
    assert (await client.post("/users/me/change-email", json={"new_email": "a@b.com", "password": "x"})).status_code in (401, 403)
