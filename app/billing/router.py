from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing import service
from app.billing.schemas import CheckoutRequest, CheckoutResult, PlanOut, SubscriptionOut, UsageOut
from app.dependencies import get_current_user, get_db
from app.users.models import User

router = APIRouter()
usage_router = APIRouter()


@router.get("/plans", response_model=list[PlanOut])
async def plans():
    return service.list_plans()


@router.get("/subscription", response_model=SubscriptionOut)
async def my_subscription(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await service.subscription_summary(db, user.id)


@router.post("/checkout", response_model=CheckoutResult)
async def checkout(
    payload: CheckoutRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await service.checkout(db, user.id, payload.plan_id)


@usage_router.get("/me", response_model=UsageOut)
async def my_usage(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await service.get_usage(db, user.id)
