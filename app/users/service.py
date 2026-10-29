from sqlalchemy.ext.asyncio import AsyncSession

from app.users.models import User


async def update_user_profile(db: AsyncSession, user: User, full_name: str | None) -> User:
    if full_name is not None:
        user.full_name = full_name
    await db.commit()
    await db.refresh(user)
    return user


async def deactivate_user(db: AsyncSession, user: User) -> None:
    # Soft delete: we deactivate rather than hard-delete, so conversation
    # history and audit trails referencing this user stay intact.
    user.is_active = False
    await db.commit()


# ---------------------------------------------------------------------------
# Account settings: change password, change email (verified by code).
# ---------------------------------------------------------------------------

import hmac
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import status as http_status
from sqlalchemy import select

from app.auth.password import hash_password, verify_password
from app.auth.service import _as_utc, _hash_code
from app.common.email_client import send_email
from app.common.exceptions import AppException, ConflictError, ForbiddenError
from app.users.models import EmailChangeCode
from config.settings import get_settings

MAX_CODE_ATTEMPTS = 5
RESEND_COOLDOWN_SECONDS = 60


def _check_password(user: User, password: str) -> None:
    # 403, not 401: the user IS logged in, the password check failed.
    if not verify_password(password, user.hashed_password):
        raise ForbiddenError("Password is incorrect")


async def change_password(db: AsyncSession, user: User, current_password: str, new_password: str) -> None:
    _check_password(user, current_password)
    if verify_password(new_password, user.hashed_password):
        raise AppException(http_status.HTTP_400_BAD_REQUEST, "New password must be different from the current one")
    user.hashed_password = hash_password(new_password)
    await db.commit()


async def request_email_change(db: AsyncSession, user: User, new_email: str, password: str) -> None:
    _check_password(user, password)

    if new_email.lower() == user.email.lower():
        raise AppException(http_status.HTTP_400_BAD_REQUEST, "That is already your email")
    taken = await db.execute(select(User).where(User.email == new_email))
    if taken.scalar_one_or_none() is not None:
        raise ConflictError("An account with this email already exists")

    now = datetime.now(timezone.utc)
    settings = get_settings()

    open_codes = (
        await db.execute(
            select(EmailChangeCode).where(EmailChangeCode.user_id == user.id, EmailChangeCode.used.is_(False))
        )
    ).scalars().all()
    for row in open_codes:
        issued_at = _as_utc(row.expires_at) - timedelta(minutes=settings.password_reset_code_minutes)
        if row.new_email == new_email and (now - issued_at).total_seconds() < RESEND_COOLDOWN_SECONDS:
            return  # a code for this address just went out
        row.used = True  # only the newest request is valid

    code = f"{secrets.randbelow(1_000_000):06d}"
    db.add(
        EmailChangeCode(
            user_id=user.id,
            new_email=new_email,
            code_hash=_hash_code(code),
            expires_at=now + timedelta(minutes=settings.password_reset_code_minutes),
        )
    )
    await db.commit()

    await send_email(
        to=new_email,
        subject="Confirm your new email for Smart Legal Advisory",
        body=(
            f"Your confirmation code is: {code}\n\n"
            f"Enter it in the app to make {new_email} your account email. "
            f"It expires in {settings.password_reset_code_minutes} minutes.\n\n"
            "If you didn't ask for this, you can ignore this email.\n\n"
            "Smart Legal Advisory System"
        ),
    )


async def confirm_email_change(db: AsyncSession, user: User, code: str) -> User:
    invalid = AppException(http_status.HTTP_400_BAD_REQUEST, "Invalid or expired code")

    result = await db.execute(
        select(EmailChangeCode)
        .where(EmailChangeCode.user_id == user.id, EmailChangeCode.used.is_(False))
        .order_by(EmailChangeCode.created_at.desc(), EmailChangeCode.expires_at.desc())
        .limit(1)
    )
    pending = result.scalar_one_or_none()
    if pending is None or _as_utc(pending.expires_at) < datetime.now(timezone.utc):
        raise invalid

    if not hmac.compare_digest(pending.code_hash, _hash_code(code)):
        pending.attempts += 1
        if pending.attempts >= MAX_CODE_ATTEMPTS:
            pending.used = True
        await db.commit()
        raise invalid

    # Someone may have registered the address since the code was sent.
    taken = await db.execute(select(User).where(User.email == pending.new_email))
    if taken.scalar_one_or_none() is not None:
        pending.used = True
        await db.commit()
        raise ConflictError("An account with this email already exists")

    old_email = user.email
    user.email = pending.new_email
    pending.used = True
    await db.commit()
    await db.refresh(user)

    # Let the old address know, in case this wasn't the owner.
    await send_email(
        to=old_email,
        subject="Your Smart Legal Advisory email was changed",
        body=(
            f"The email on your account was changed to {user.email}.\n\n"
            "If you didn't do this, please contact support right away.\n\n"
            "Smart Legal Advisory System"
        ),
    )
    return user
