from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import create_access_token, create_refresh_token, decode_token, TokenType
from app.auth.password import hash_password, verify_password
from app.auth.schemas import TokenResponse
from app.common.exceptions import ConflictError, UnauthorizedError
from app.users.models import User
from jose import JWTError


async def register_user(
    db: AsyncSession, email: str, password: str, full_name: str | None
) -> User:
    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none() is not None:
        raise ConflictError("An account with this email already exists")

    user = User(email=email, hashed_password=hash_password(password), full_name=full_name)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(password, user.hashed_password):
        # Deliberately vague: don't reveal whether the email or password was wrong.
        raise UnauthorizedError("Incorrect email or password")

    if not user.is_active:
        raise UnauthorizedError("This account has been deactivated")

    return user


def issue_tokens(user_id: str) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(user_id),
        refresh_token=create_refresh_token(user_id),
    )


def refresh_access_token(refresh_token: str) -> TokenResponse:
    try:
        payload = decode_token(refresh_token)
    except JWTError:
        raise UnauthorizedError("Invalid or expired refresh token")

    if payload.get("type") != TokenType.REFRESH.value:
        raise UnauthorizedError("Token is not a refresh token")

    user_id = payload["sub"]
    return issue_tokens(user_id)


# ---------------------------------------------------------------------------
# Forgot password: email a 6-digit code, then reset with that code.
# ---------------------------------------------------------------------------

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import status as http_status

from app.auth.models import PasswordResetCode
from app.common.email_client import send_email
from app.common.exceptions import AppException
from config.settings import get_settings

MAX_CODE_ATTEMPTS = 5
RESEND_COOLDOWN_SECONDS = 60


def _hash_code(code: str) -> str:
    # Keyed hash: a leaked database alone is not enough to check codes.
    key = get_settings().jwt_secret_key.encode()
    return hmac.new(key, code.encode(), hashlib.sha256).hexdigest()


def _as_utc(dt: datetime) -> datetime:
    # SQLite returns naive datetimes; treat them as UTC.
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


async def _latest_open_code(db: AsyncSession, user_id: str) -> PasswordResetCode | None:
    result = await db.execute(
        select(PasswordResetCode)
        .where(PasswordResetCode.user_id == user_id, PasswordResetCode.used.is_(False))
        .order_by(PasswordResetCode.created_at.desc(), PasswordResetCode.expires_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def request_password_reset(db: AsyncSession, email: str) -> None:
    """
    Email a reset code if an active account exists. Always returns quietly,
    so the API never reveals which emails are registered.
    """
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        return

    now = datetime.now(timezone.utc)
    settings = get_settings()

    # Don't send a new email if one went out less than a minute ago.
    latest = await _latest_open_code(db, user.id)
    if latest is not None:
        issued_at = _as_utc(latest.expires_at) - timedelta(minutes=settings.password_reset_code_minutes)
        if (now - issued_at).total_seconds() < RESEND_COOLDOWN_SECONDS:
            return

    # Only the newest code is valid: close any older ones.
    old = await db.execute(
        select(PasswordResetCode).where(
            PasswordResetCode.user_id == user.id, PasswordResetCode.used.is_(False)
        )
    )
    for code_row in old.scalars().all():
        code_row.used = True

    code = f"{secrets.randbelow(1_000_000):06d}"
    db.add(
        PasswordResetCode(
            user_id=user.id,
            code_hash=_hash_code(code),
            expires_at=now + timedelta(minutes=settings.password_reset_code_minutes),
        )
    )
    await db.commit()

    await send_email(
        to=user.email,
        subject="Your Smart Legal Advisory password reset code",
        body=(
            f"Hello{(' ' + user.full_name) if user.full_name else ''},\n\n"
            f"Your password reset code is: {code}\n\n"
            f"It expires in {settings.password_reset_code_minutes} minutes. "
            "If you didn't ask to reset your password, you can ignore this email.\n\n"
            "Smart Legal Advisory System"
        ),
    )


async def reset_password(db: AsyncSession, email: str, code: str, new_password: str) -> None:
    invalid = AppException(http_status.HTTP_400_BAD_REQUEST, "Invalid or expired code")

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise invalid

    reset = await _latest_open_code(db, user.id)
    if reset is None or _as_utc(reset.expires_at) < datetime.now(timezone.utc):
        raise invalid

    if not hmac.compare_digest(reset.code_hash, _hash_code(code)):
        reset.attempts += 1
        if reset.attempts >= MAX_CODE_ATTEMPTS:
            reset.used = True  # too many wrong guesses: this code is dead
        await db.commit()
        raise invalid

    user.hashed_password = hash_password(new_password)
    reset.used = True
    await db.commit()



# ---------------------------------------------------------------------------
# Continue with Google: verify Google's ID token, then log in or sign up.
# ---------------------------------------------------------------------------


def verify_google_id_token(token: str) -> dict:
    """Checks the token's signature, expiry and audience with Google's keys.
    Kept as its own function so tests can replace it."""
    from google.auth.transport import requests as google_requests
    from google.oauth2 import id_token as google_id_token

    return google_id_token.verify_oauth2_token(token, google_requests.Request())


async def login_with_google(db: AsyncSession, token: str) -> TokenResponse:
    settings = get_settings()
    allowed = settings.google_client_ids_list
    if not allowed:
        raise AppException(http_status.HTTP_503_SERVICE_UNAVAILABLE, "Google sign-in is not set up on the server yet")

    invalid = UnauthorizedError("Google sign-in failed. Please try again.")
    try:
        info = verify_google_id_token(token)
    except Exception:
        raise invalid

    if info.get("aud") not in allowed:
        raise invalid
    if not info.get("email") or not info.get("email_verified"):
        raise UnauthorizedError("Your Google account email is not verified")

    email = info["email"].lower()
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user is None:
        # New user: create the account. They get a random password they don't
        # know; they can set one later via "Forgot password".
        user = User(
            email=email,
            hashed_password=hash_password(secrets.token_urlsafe(32)),
            full_name=info.get("name"),
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    elif not user.is_active:
        raise UnauthorizedError("This account has been deactivated")

    # Same email already registered with a password: Google has proven the
    # user owns that email, so this logs into the existing account.
    return issue_tokens(user.id)
