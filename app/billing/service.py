"""
Plans, demo checkout and the free-plan question allowance.

Free plan: FREE_QUERY_LIMIT questions; once they are used up the user waits
FREE_REFRESH_HOURS (counted from the moment the limit was reached) before the
counter resets. Paid plans (monthly / quarterly) are unlimited until they expire.
This mirrors the web app's own rules so both sides agree.
"""

import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing.models import FreeUsage, Payment, Subscription
from app.common.exceptions import AppException
from config.constants import FREE_PLAN_ID, FREE_QUERY_LIMIT, FREE_REFRESH_HOURS, PLANS


def _utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def list_plans() -> list[dict]:
    return [{"id": pid, **info} for pid, info in PLANS.items()]


async def get_subscription(db: AsyncSession, user_id: str) -> Subscription | None:
    """The user's paid subscription if it is still running, else None."""
    sub = (await db.execute(select(Subscription).where(Subscription.user_id == user_id))).scalar_one_or_none()
    if sub is None or sub.status != "active" or _utc(sub.expires_at) <= datetime.now(timezone.utc):
        return None
    return sub


async def subscription_summary(db: AsyncSession, user_id: str) -> dict:
    sub = await get_subscription(db, user_id)
    if sub is None:
        return {"plan_id": FREE_PLAN_ID, "status": "active", "started_at": None, "expires_at": None}
    return {"plan_id": sub.plan_id, "status": sub.status, "started_at": sub.started_at, "expires_at": sub.expires_at}


async def checkout(db: AsyncSession, user_id: str, plan_id: str) -> dict:
    """
    DEMO checkout: confirms the plan immediately and records a payment with a
    DEMO- reference. No card is charged and no payment gateway is called. To go
    live, create the gateway charge here and only activate on its confirmation.
    """
    plan = PLANS.get(plan_id)
    if plan is None or plan["period_days"] is None:
        raise AppException(400, "Choose the monthly or quarterly plan")

    now = datetime.now(timezone.utc)
    sub = (await db.execute(select(Subscription).where(Subscription.user_id == user_id))).scalar_one_or_none()
    # Renewing early keeps the days already paid for.
    base = now
    if sub is not None and sub.status == "active" and _utc(sub.expires_at) > now:
        base = _utc(sub.expires_at)
    expires_at = base + timedelta(days=plan["period_days"])

    if sub is None:
        sub = Subscription(user_id=user_id, plan_id=plan_id, status="active", started_at=now, expires_at=expires_at)
        db.add(sub)
    else:
        sub.plan_id, sub.status, sub.started_at, sub.expires_at = plan_id, "active", now, expires_at

    reference = f"DEMO-{secrets.token_hex(4).upper()}"
    db.add(Payment(user_id=user_id, plan_id=plan_id, amount_pkr=plan["price_pkr"], reference=reference, paid_at=now))
    await db.commit()
    return {"reference": reference, "plan_id": plan_id, "paid_at": now, "expires_at": expires_at, "demo": True}


async def _get_or_create_usage(db: AsyncSession, user_id: str) -> FreeUsage:
    usage = (await db.execute(select(FreeUsage).where(FreeUsage.user_id == user_id))).scalar_one_or_none()
    if usage is None:
        usage = FreeUsage(user_id=user_id, used=0, limit_reached_at=None)
        db.add(usage)
        await db.flush()
    return usage


def _refresh_if_due(usage: FreeUsage, now: datetime) -> None:
    reached = _utc(usage.limit_reached_at)
    if reached is not None and now >= reached + timedelta(hours=FREE_REFRESH_HOURS):
        usage.used = 0
        usage.limit_reached_at = None


async def get_usage(db: AsyncSession, user_id: str) -> dict:
    sub = await get_subscription(db, user_id)
    if sub is not None:
        return {
            "plan_id": sub.plan_id, "unlimited": True, "used": 0, "limit": None,
            "remaining": None, "limit_reached_at": None, "reset_at": None,
        }
    usage = await _get_or_create_usage(db, user_id)
    _refresh_if_due(usage, datetime.now(timezone.utc))
    await db.commit()
    reached = _utc(usage.limit_reached_at)
    return {
        "plan_id": FREE_PLAN_ID,
        "unlimited": False,
        "used": usage.used,
        "limit": FREE_QUERY_LIMIT,
        "remaining": max(0, FREE_QUERY_LIMIT - usage.used),
        "limit_reached_at": reached,
        "reset_at": reached + timedelta(hours=FREE_REFRESH_HOURS) if reached else None,
    }


async def ensure_can_ask(db: AsyncSession, user_id: str) -> None:
    """Raise HTTP 402 when a free-plan user has no questions left."""
    usage = await get_usage(db, user_id)
    if not usage["unlimited"] and usage["remaining"] == 0:
        raise AppException(
            402,
            f"You've used all {FREE_QUERY_LIMIT} free questions. "
            "Upgrade your plan or wait for the allowance to reset.",
        )


async def record_query(db: AsyncSession, user_id: str) -> None:
    """Count one delivered answer against the free allowance (paid plans are not counted)."""
    if await get_subscription(db, user_id) is not None:
        return
    usage = await _get_or_create_usage(db, user_id)
    now = datetime.now(timezone.utc)
    _refresh_if_due(usage, now)
    usage.used += 1
    if usage.used >= FREE_QUERY_LIMIT and usage.limit_reached_at is None:
        usage.limit_reached_at = now
    await db.commit()
