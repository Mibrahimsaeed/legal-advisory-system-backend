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
