"""
Shared FastAPI Depends() used across multiple routers.
"""

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import TokenType, decode_token
from app.common.exceptions import UnauthorizedError
from app.users.models import User
from db.session import get_db  # re-exported: `from app.dependencies import get_db`

__all__ = ["get_db", "get_current_user"]

_bearer_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    FastAPI dependency that reads the "Authorization: Bearer <token>" header,
    validates the JWT, and returns the matching User row.
    Use this on any route that should only be reachable while logged in:

        @router.get("/me")
        async def me(user: User = Depends(get_current_user)): ...
    """
    token = credentials.credentials
    try:
        payload = decode_token(token)
    except JWTError:
        raise UnauthorizedError("Invalid or expired access token")

    if payload.get("type") != TokenType.ACCESS.value:
        raise UnauthorizedError("Token is not an access token")

    user_id = payload["sub"]
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise UnauthorizedError("User no longer exists")
    if not user.is_active:
        raise UnauthorizedError("This account has been deactivated")

    return user

