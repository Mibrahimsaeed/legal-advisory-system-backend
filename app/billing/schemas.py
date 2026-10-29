from datetime import datetime

from pydantic import BaseModel, Field


class PlanOut(BaseModel):
    id: str
    name: str
    price_pkr: int
    period_days: int | None  # None = no billing period (free)


class SubscriptionOut(BaseModel):
    plan_id: str  # "free" when there is no active paid plan
    status: str
    started_at: datetime | None = None
    expires_at: datetime | None = None


class CheckoutRequest(BaseModel):
    plan_id: str = Field(pattern="^(monthly|quarterly)$")


class CheckoutResult(BaseModel):
    """Demo confirmation: no real payment gateway is called (see service.checkout)."""
    reference: str
    plan_id: str
    paid_at: datetime
    expires_at: datetime
    demo: bool = True


class UsageOut(BaseModel):
    plan_id: str
    unlimited: bool
    used: int
    limit: int | None  # None when unlimited
    remaining: int | None
    limit_reached_at: datetime | None = None
    reset_at: datetime | None = None
