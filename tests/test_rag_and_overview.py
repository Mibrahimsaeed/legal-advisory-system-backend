"""Admin: RAG source submission, dashboard overview, plan/chat counts and user deletion."""

import pytest

from app.billing.models import Payment
from db.session import AsyncSessionLocal
from sqlalchemy import select

pytestmark = pytest.mark.asyncio

STATUTE = {
    "title": "Constitution of Pakistan", "document_type": "statute", "jurisdiction": "Pakistan",
    "year": "1973", "category": "Constitutional", "description": "Fundamental law", "source": "pakistancode.gov.pk",
}


async def test_rag_requires_admin(client, make_user):
    user, _ = await make_user("rag.user@example.com")
    assert (await client.post("/admin/rag/documents", headers=user, data={**STATUTE, "content": "x"})).status_code == 403
    assert (await client.get("/admin/rag/jobs/abc", headers=user)).status_code == 403
    assert (await client.post("/admin/rag/documents", data={**STATUTE, "content": "x"})).status_code in (401, 403)


async def test_rag_text_submission_completes(client, make_user):
    admin, _ = await make_user("rag.admin1@example.com", admin=True)
    r = await client.post("/admin/rag/documents", headers=admin, data={**STATUTE, "content": "Article 1. Pakistan is a Republic."})
    assert r.status_code == 202
    sub = r.json()
    assert sub["title"] == "Constitution of Pakistan" and sub["document_type"] == "statute" and sub["job_id"]

    job = (await client.get(f"/admin/rag/jobs/{sub['job_id']}", headers=admin)).json()
    assert job["status"] == "completed" and job["completed_at"] and job["error_message"] is None


async def test_rag_file_submission(client, make_user):
    admin, _ = await make_user("rag.admin2@example.com", admin=True)
    r = await client.post(
        "/admin/rag/documents", headers=admin, data={**STATUTE, "document_type": "act"},
        files={"file": ("act.txt", b"Section 1. Short title.", "text/plain")},
    )
    assert r.status_code == 202
    job = (await client.get(f"/admin/rag/jobs/{r.json()['job_id']}", headers=admin)).json()
    assert job["status"] == "completed"


async def test_rag_validation(client, make_user):
    admin, _ = await make_user("rag.admin3@example.com", admin=True)
    no_body = await client.post("/admin/rag/documents", headers=admin, data=STATUTE)
    assert no_body.status_code == 422
    bad_type = await client.post("/admin/rag/documents", headers=admin, data={**STATUTE, "document_type": "memo", "content": "x"})
    assert bad_type.status_code == 422
    bad_file = await client.post(
        "/admin/rag/documents", headers=admin, data=STATUTE,
        files={"file": ("pic.png", b"\x89PNG", "image/png")},
    )
    assert bad_file.status_code == 415
    assert (await client.get("/admin/rag/jobs/does-not-exist", headers=admin)).status_code == 404


async def test_rag_unreadable_file_marks_job_failed(client, make_user):
    admin, _ = await make_user("rag.admin4@example.com", admin=True)
    r = await client.post(
        "/admin/rag/documents", headers=admin, data=STATUTE,
        files={"file": ("empty.txt", b"   ", "text/plain")},
    )
    job = (await client.get(f"/admin/rag/jobs/{r.json()['job_id']}", headers=admin)).json()
    assert job["status"] == "failed" and "readable" in job["error_message"]


async def test_overview_shape_and_numbers(client, make_user):
    admin, _ = await make_user("ov.admin@example.com", admin=True)
    payer, _ = await make_user("ov.payer@example.com")
    free, _ = await make_user("ov.free@example.com")
    conv = (await client.post("/conversations", headers=free, json={})).json()["id"]
    await client.post(f"/chat/{conv}/message", headers=free, json={"question": "Hi"})
    await client.post("/billing/checkout", headers=payer, json={"plan_id": "quarterly"})
    await client.post("/admin/rag/documents", headers=admin, data={**STATUTE, "content": "text"})

    r = await client.get("/admin/overview", headers=admin)
    assert r.status_code == 200
    o = r.json()
    assert set(o) == {"stats", "userGrowth", "revenue", "queries", "userDistribution", "subscribersByPlan"}
    assert set(o["stats"]) == {"totalUsers", "activeUsers", "newUsers", "totalQueries", "freeChatsUsed",
                               "paidUsers", "monthlyRevenue", "ragDocuments"}
    st = o["stats"]
    assert st["totalUsers"] >= 3 and st["paidUsers"] >= 1 and st["monthlyRevenue"] >= 11000
    assert st["totalQueries"] >= 1 and st["freeChatsUsed"] >= 1 and st["ragDocuments"] >= 1
    assert st["activeUsers"] >= 1 and st["newUsers"] >= 3

    for series in ("userGrowth", "revenue", "queries"):
        assert len(o[series]) == 6 and all(set(p) == {"month", "value"} for p in o[series])
    assert o["userGrowth"][-1]["value"] == st["totalUsers"]  # cumulative: last month = all users today
    assert o["revenue"][-1]["value"] == st["monthlyRevenue"]
    assert [d["label"] for d in o["userDistribution"]] == ["Free users", "Paid users", "Admins"]
    assert [d["label"] for d in o["subscribersByPlan"]] == ["Monthly plan", "Quarterly plan"]
    assert dict((d["label"], d["value"]) for d in o["subscribersByPlan"])["Quarterly plan"] >= 1


async def test_overview_requires_admin(client, make_user):
    user, _ = await make_user("ov.nobody@example.com")
    assert (await client.get("/admin/overview", headers=user)).status_code == 403
    assert (await client.get("/admin/overview")).status_code in (401, 403)


async def test_admin_users_include_plan_and_chat_count(client, make_user):
    admin, _ = await make_user("au.admin@example.com", admin=True)
    member, uid = await make_user("au.member@example.com")
    conv = (await client.post("/conversations", headers=member, json={})).json()["id"]
    for q in ("one", "two"):
        await client.post(f"/chat/{conv}/message", headers=member, json={"question": q})
    await client.post("/billing/checkout", headers=member, json={"plan_id": "monthly"})

    items = (await client.get("/admin/users", headers=admin, params={"q": "au.member"})).json()["items"]
    assert items[0]["plan"] == "monthly" and items[0]["chats_used"] == 2


async def test_admin_can_delete_user_and_data_but_keeps_payments(client, make_user):
    admin, _ = await make_user("del.admin@example.com", admin=True)
    victim, vid = await make_user("del.victim@example.com")
    conv = (await client.post("/conversations", headers=victim, json={})).json()["id"]
    await client.post(f"/chat/{conv}/message", headers=victim, json={"question": "Hello"})
    await client.post("/documents/upload", headers=victim, files={"file": ("a.txt", b"hello", "text/plain")})
    await client.post("/billing/checkout", headers=victim, json={"plan_id": "monthly"})

    assert (await client.delete(f"/admin/users/{vid}", headers=admin)).status_code == 204

    assert (await client.get("/admin/users", headers=admin, params={"q": "del.victim"})).json()["total"] == 0
    assert (await client.get("/users/me", headers=victim)).status_code == 401  # account is gone
    async with AsyncSessionLocal() as db:
        kept = (await db.execute(select(Payment).where(Payment.user_id == vid))).scalars().all()
    assert len(kept) == 1  # revenue history survives
    audit = (await client.get("/admin/audit", headers=admin)).json()["items"]
    assert any(a["action"] == "user_deleted" and a["target"] == "del.victim@example.com" for a in audit)


async def test_delete_user_guards(client, make_user):
    admin, aid = await make_user("guard.admin@example.com", admin=True)
    _, other_admin_id = await make_user("guard.admin2@example.com", admin=True)
    normal, nid = await make_user("guard.normal@example.com")

    assert (await client.delete(f"/admin/users/{aid}", headers=admin)).status_code == 400  # self
    assert (await client.delete(f"/admin/users/{other_admin_id}", headers=admin)).status_code == 400  # other admin
    assert (await client.delete("/admin/users/no-such-id", headers=admin)).status_code == 404
    assert (await client.delete(f"/admin/users/{nid}", headers=normal)).status_code == 403  # not an admin
    assert (await client.get("/users/me", headers=normal)).status_code == 200  # untouched
