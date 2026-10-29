"""Continue with Google: Google's token check is replaced with a fake in tests."""

import pytest

from app.auth import service as auth_service
from config.settings import get_settings

pytestmark = pytest.mark.asyncio

CLIENT_ID = "test-web-client.apps.googleusercontent.com"


@pytest.fixture
def google(monkeypatch):
    monkeypatch.setattr(get_settings(), "google_client_ids", CLIENT_ID)
    tokens = {}

    def fake_verify(token):
        if token not in tokens:
            raise ValueError("bad token")
        return tokens[token]

    monkeypatch.setattr(auth_service, "verify_google_id_token", fake_verify)
    return tokens


async def test_google_creates_account_then_logs_in(client, google):
    google["tok-new-user"] = {"aud": CLIENT_ID, "email": "G.User@gmail.com", "email_verified": True, "name": "G User"}
    r = await client.post("/auth/google", json={"id_token": "tok-new-user"})
    assert r.status_code == 200 and "access_token" in r.json()
    me = await client.get("/users/me", headers={"Authorization": f"Bearer {r.json()['access_token']}"})
    assert me.json()["email"] == "g.user@gmail.com" and me.json()["full_name"] == "G User"
    # second time: same account, no duplicate
    r2 = await client.post("/auth/google", json={"id_token": "tok-new-user"})
    me2 = await client.get("/users/me", headers={"Authorization": f"Bearer {r2.json()['access_token']}"})
    assert me2.json()["id"] == me.json()["id"]


async def test_google_joins_existing_email_account(client, google):
    await client.post("/auth/register", json={"email": "both@gmail.com", "password": "password123"})
    google["tok-both-accounts"] = {"aud": CLIENT_ID, "email": "both@gmail.com", "email_verified": True}
    r = await client.post("/auth/google", json={"id_token": "tok-both-accounts"})
    assert r.status_code == 200
    # password login still works too
    assert (await client.post("/auth/login", json={"email": "both@gmail.com", "password": "password123"})).status_code == 200


async def test_google_rejects_bad_tokens(client, google):
    google["tok-wrong-aud"] = {"aud": "someone-else", "email": "x@gmail.com", "email_verified": True}
    google["tok-unverified"] = {"aud": CLIENT_ID, "email": "y@gmail.com", "email_verified": False}
    assert (await client.post("/auth/google", json={"id_token": "tok-garbage-xyz"})).status_code == 401
    assert (await client.post("/auth/google", json={"id_token": "tok-wrong-aud"})).status_code == 401
    assert (await client.post("/auth/google", json={"id_token": "tok-unverified"})).status_code == 401


async def test_google_disabled_without_client_ids(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "google_client_ids", "")
    r = await client.post("/auth/google", json={"id_token": "anything-long"})
    assert r.status_code == 503
