from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import service
from app.auth.jwt import decode_token
from app.auth.schemas import (
    ForgotPasswordRequest,
    GoogleLoginRequest,
    LoginRequest,
    LogoutRequest,
    MessageResponse,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
)
from app.dependencies import get_db
from app.users.schemas import UserProfile
from jose import JWTError

router = APIRouter()

# In-memory blocklist for revoked refresh tokens (logout).
# NOTE: this resets when the server restarts. For production, move this to
# Redis (settings.redis_url is already configured) so revocation survives restarts.
_revoked_tokens: set[str] = set()


@router.post("/register", response_model=UserProfile, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)):
    user = await service.register_user(db, payload.email, payload.password, payload.full_name)
    return user


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = await service.authenticate_user(db, payload.email, payload.password)
    return service.issue_tokens(user.id)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(payload: RefreshRequest):
    if payload.refresh_token in _revoked_tokens:
        from app.common.exceptions import UnauthorizedError
        raise UnauthorizedError("This token has been revoked, please log in again")
    return service.refresh_access_token(payload.refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(payload: LogoutRequest):
    # Verify it's a real token before blocklisting it (avoids blocklist spam).
    try:
        decode_token(payload.refresh_token)
    except JWTError:
        pass  # already invalid/expired — nothing to revoke
    else:
        _revoked_tokens.add(payload.refresh_token)
    return None


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(payload: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    """Email a 6-digit reset code. Same answer whether or not the email exists."""
    await service.request_password_reset(db, payload.email)
    return MessageResponse(
        message="If an account exists for this email, a reset code has been sent."
    )


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(payload: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    await service.reset_password(db, payload.email, payload.code, payload.new_password)
    return MessageResponse(message="Your password has been changed. Please log in.")


@router.post("/google", response_model=TokenResponse)
async def login_with_google(payload: GoogleLoginRequest, db: AsyncSession = Depends(get_db)):
    """Continue with Google: works for both sign up and log in."""
    return await service.login_with_google(db, payload.id_token)
