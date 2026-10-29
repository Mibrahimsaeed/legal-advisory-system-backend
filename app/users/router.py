from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db
from app.users import service
from app.users.models import User
from app.auth.password import verify_password
from app.common.exceptions import ForbiddenError
from app.users.schemas import (
    ChangeEmailRequest,
    ChangePasswordRequest,
    ConfirmEmailChangeRequest,
    DeleteAccountRequest,
    MessageResponse,
    UserProfile,
    UserUpdate,
)

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
    payload: DeleteAccountRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Re-check identity: the logged-in session alone is not enough.
    email_matches = payload.email.strip().lower() == user.email.lower()
    if not email_matches or not verify_password(payload.password, user.hashed_password):
        raise ForbiddenError("Email or password is incorrect")

    await service.deactivate_user(db, user)
    return None


@router.post("/me/change-password", response_model=MessageResponse)
async def change_my_password(
    payload: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await service.change_password(db, user, payload.current_password, payload.new_password)
    return MessageResponse(message="Your password has been changed.")


@router.post("/me/change-email", response_model=MessageResponse)
async def request_email_change(
    payload: ChangeEmailRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Step 1: check the password, then email a 6-digit code to the NEW address."""
    await service.request_email_change(db, user, payload.new_email, payload.password)
    return MessageResponse(message=f"We sent a 6-digit code to {payload.new_email}.")


@router.post("/me/change-email/confirm", response_model=UserProfile)
async def confirm_email_change(
    payload: ConfirmEmailChangeRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Step 2: the code from the new inbox. Returns the updated profile."""
    return await service.confirm_email_change(db, user, payload.code)
