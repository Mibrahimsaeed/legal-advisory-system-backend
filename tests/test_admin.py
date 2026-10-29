"""Admin dashboard API: access control, privacy, and actions."""

import pytest
from sqlalchemy import update

from app.users.models import User
from db.session import AsyncSessionLocal

pytestmark = pytest.mark.asyncio
PW = "adminpass123"


async def _login(client, email, admin=False, name="Person"):
    await client.post("/auth/register", json={"email": email, "password": PW, "full_name": name})
    if admin:
        async with AsyncSessionLocal() as db:
            await db.execute(update(User).where(User.email == email).values(is_admin=True))
            await db.commit()
    r = await client.post("/auth/login", json={"email": email, "password": PW})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def test_admin_routes_blocked_for_normal_users(client):
    h = await _login(client, "normal.user@example.com")
    for path in ["/admin/me", "/admin/stats", "/admin/users", "/admin/questions", "/admin/documents", "/admin/system", "/admin/audit"]:
        assert (await client.get(path, headers=h)).status_code == 403, path
    assert (await client.get("/admin/stats")).status_code in (401, 403)


async def test_stats_and_privacy(client):
    admin = await _login(client, "boss@example.com", admin=True, name="Boss")
    user = await _login(client, "asker@example.com", name="Secret Name")
    conv = (await client.post("/conversations", headers=user, json={"title": "x"})).json()
    await client.post(f"/chat/{conv['id']}/message", headers=user, json={"question": "How do I file for divorce and custody?"})
    await client.post("/documents/upload", headers=user, files={"file": ("lease.txt", b"private lease text", "text/plain")})

    s = (await client.get("/admin/stats", headers=admin)).json()
    assert s["total_questions"] >= 1 and len(s["questions_per_day"]) == 30
    assert any(t["label"] == "Family law" for t in s["topics"])

    qs = (await client.get("/admin/questions", headers=admin)).json()
    item = next(i for i in qs["items"] if "divorce" in i["question"])
    assert item["topic"] == "Family law"
    assert item["user_ref"].startswith("User ")
    raw = str(qs)
    assert "asker@example.com" not in raw and "Secret Name" not in raw
    assert "Simulated response" not in raw  # answers never included

    docs = (await client.get("/admin/documents", headers=admin)).json()
    d = next(i for i in docs["items"] if i["original_filename"] == "lease.txt")
    assert d["file_type"] == "Text" and "private lease text" not in str(docs)
    assert "asker@example.com" not in str(docs)


async def test_deactivate_reactivate_and_audit(client):
    admin = await _login(client, "chief@example.com", admin=True)
    await _login(client, "target@example.com")
    users = (await client.get("/admin/users", headers=admin, params={"q": "target@"})).json()
    target = users["items"][0]

    r = await client.patch(f"/admin/users/{target['id']}", headers=admin, json={"is_active": False})
    assert r.status_code == 200 and r.json()["is_active"] is False
    assert (await client.post("/auth/login", json={"email": "target@example.com", "password": PW})).status_code == 401

    r = await client.patch(f"/admin/users/{target['id']}", headers=admin, json={"is_active": True})
    assert r.json()["is_active"] is True
    assert (await client.post("/auth/login", json={"email": "target@example.com", "password": PW})).status_code == 200

    audit = (await client.get("/admin/audit", headers=admin)).json()
    actions = [a["action"] for a in audit["items"] if a["target"] == "target@example.com"]
    assert actions[:2] == ["user_reactivated", "user_deactivated"]


async def test_admin_cannot_deactivate_self(client):
    admin = await _login(client, "self.admin@example.com", admin=True)
    me = (await client.get("/admin/me", headers=admin)).json()
    r = await client.patch(f"/admin/users/{me['id']}", headers=admin, json={"is_active": False})
    assert r.status_code == 400


async def test_system_status(client):
    admin = await _login(client, "sys.admin@example.com", admin=True)
    s = (await client.get("/admin/system", headers=admin)).json()
    names = {x["name"]: x["status"] for x in s["services"]}
    assert names["Database"] == "ok" and names["AI answer pipeline"] == "simulated"


def test_topic_classifier_uses_whole_words():
    from app.admin.service import classify_topic

    assert classify_topic("My employer fired me without notice") == "Labour & employment"
    assert classify_topic("Police refused to register my FIR") == "Criminal law"
    assert classify_topic("Can my husband marry again?") == "Family law"
    assert classify_topic("How do I get a succession certificate?") == "Property law"
    assert classify_topic("What does Article 25 say?") == "Constitutional rights"
    assert classify_topic("Hello, how are you?") == "Other"
