"""Plans, demo checkout and the free-plan allowance (6 questions, then wait or upgrade)."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select, update

from app.billing.models import FreeUsage, Subscription
from db.session import AsyncSessionLocal

pytestmark = pytest.mark.asyncio


async def _ask(client, headers, conv_id, text="Question?"):
    return await client.post(f"/chat/{conv_id}/message", headers=headers, json={"question": text})


async def _new_conversation(client, headers):
    return (await client.post("/conversations", headers=headers, json={})).json()["id"]


async def test_plans_listed(client, make_user):
    h, _ = await make_user("bill.plans@example.com")
    plans = {p["id"]: p for p in (await client.get("/billing/plans", headers=h)).json()}
    assert plans["free"]["price_pkr"] == 0 and plans["free"]["period_days"] is None
    assert plans["monthly"]["price_pkr"] == 4000 and plans["monthly"]["period_days"] == 30
    assert plans["quarterly"]["price_pkr"] == 11000 and plans["quarterly"]["period_days"] == 90


async def test_free_allowance_then_402_and_nothing_saved(client, make_user):
    h, _ = await make_user("bill.free@example.com")
    usage = (await client.get("/usage/me", headers=h)).json()
    assert usage["plan_id"] == "free" and usage["unlimited"] is False
    assert (usage["used"], usage["limit"], usage["remaining"]) == (0, 6, 6)

    conv = await _new_conversation(client, h)
    for i in range(6):
        assert (await _ask(client, h, conv, f"Q{i}")).status_code == 200

    usage = (await client.get("/usage/me", headers=h)).json()
    assert (usage["used"], usage["remaining"]) == (6, 0)
    assert usage["limit_reached_at"] and usage["reset_at"]

    blocked = await _ask(client, h, conv, "One too many")
    assert blocked.status_code == 402
    assert "free questions" in blocked.json()["detail"]
    # The refused question must not be stored.
    msgs = (await client.get(f"/conversations/{conv}/messages", headers=h, params={"limit": 100})).json()
    assert msgs["total"] == 12


async def test_checkout_unlocks_unlimited(client, make_user):
    h, _ = await make_user("bill.upgrade@example.com")
    conv = await _new_conversation(client, h)
    for _i in range(6):
        await _ask(client, h, conv)
    assert (await _ask(client, h, conv)).status_code == 402

    paid = await client.post("/billing/checkout", headers=h, json={"plan_id": "monthly"})
    assert paid.status_code == 200
    body = paid.json()
    assert body["reference"].startswith("DEMO-") and body["plan_id"] == "monthly" and body["demo"] is True

    assert (await _ask(client, h, conv)).status_code == 200
    usage = (await client.get("/usage/me", headers=h)).json()
    assert usage["unlimited"] is True and usage["limit"] is None and usage["plan_id"] == "monthly"
    sub = (await client.get("/billing/subscription", headers=h)).json()
    assert sub["plan_id"] == "monthly" and sub["expires_at"]


async def test_checkout_validation_and_auth(client, make_user):
    h, _ = await make_user("bill.invalid@example.com")
    assert (await client.post("/billing/checkout", headers=h, json={"plan_id": "free"})).status_code == 422
    assert (await client.post("/billing/checkout", headers=h, json={"plan_id": "gold"})).status_code == 422
    assert (await client.post("/billing/checkout", json={"plan_id": "monthly"})).status_code in (401, 403)
    assert (await client.get("/usage/me")).status_code in (401, 403)
    assert (await client.get("/billing/subscription", headers=h)).json()["plan_id"] == "free"


async def test_early_renewal_keeps_remaining_days(client, make_user):
    h, _ = await make_user("bill.renew@example.com")
    first = (await client.post("/billing/checkout", headers=h, json={"plan_id": "monthly"})).json()
    second = (await client.post("/billing/checkout", headers=h, json={"plan_id": "quarterly"})).json()
    gap = datetime.fromisoformat(second["expires_at"]) - datetime.fromisoformat(first["expires_at"])
    assert gap == timedelta(days=90)  # added on top of the unused month
    assert first["reference"] != second["reference"]


async def test_allowance_resets_after_wait(client, make_user):
    h, uid = await make_user("bill.reset@example.com")
    conv = await _new_conversation(client, h)
    for _i in range(6):
        await _ask(client, h, conv)
    assert (await _ask(client, h, conv)).status_code == 402

    async with AsyncSessionLocal() as db:  # pretend the limit was hit 7 hours ago (window is 6h)
        await db.execute(update(FreeUsage).where(FreeUsage.user_id == uid).values(
            limit_reached_at=datetime.now(timezone.utc) - timedelta(hours=7)))
        await db.commit()

    assert (await _ask(client, h, conv, "Back again")).status_code == 200
    usage = (await client.get("/usage/me", headers=h)).json()
    assert usage["used"] == 1 and usage["remaining"] == 5 and usage["limit_reached_at"] is None


async def test_expired_subscription_falls_back_to_free(client, make_user):
    h, uid = await make_user("bill.expired@example.com")
    await client.post("/billing/checkout", headers=h, json={"plan_id": "monthly"})
    async with AsyncSessionLocal() as db:
        await db.execute(update(Subscription).where(Subscription.user_id == uid).values(
            expires_at=datetime.now(timezone.utc) - timedelta(days=1)))
        await db.commit()
    assert (await client.get("/billing/subscription", headers=h)).json()["plan_id"] == "free"
    assert (await client.get("/usage/me", headers=h)).json()["unlimited"] is False
