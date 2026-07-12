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
