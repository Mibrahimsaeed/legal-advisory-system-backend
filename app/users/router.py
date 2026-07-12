from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db
from app.users import service
from app.users.models import User
from app.users.schemas import UserProfile, UserUpdate

router = APIRouter()


@router.get("/me", response_model=UserProfile)
async def get_my_profile(user: User = Depends(get_current_user)):
    return user


@router.patch("/me", response_model=UserProfile)
async def update_my_profile(
    payload: UserUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await service.update_user_profile(db, user, payload.full_name)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_account(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await service.deactivate_user(db, user)
    return None
