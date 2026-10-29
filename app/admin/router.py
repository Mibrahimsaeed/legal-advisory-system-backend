"""Admin dashboard API. Every route requires an admin account."""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin import service
from app.admin.schemas import (
    AdminDocumentPage,
    AdminQuestionPage,
    AdminUser,
    AdminUserPage,
    AuditPage,
    Overview,
    Stats,
    SystemStatus,
    UserStatusUpdate,
)
from app.dependencies import get_current_admin, get_db
from app.users.models import User
from app.users.schemas import UserProfile

router = APIRouter(dependencies=[Depends(get_current_admin)])


@router.get("/me", response_model=UserProfile)
async def admin_me(admin: User = Depends(get_current_admin)):
    """Lets the dashboard confirm the logged-in account is an admin."""
    return admin


@router.get("/stats", response_model=Stats)
async def stats(db: AsyncSession = Depends(get_db)):
    return await service.get_stats(db)


@router.get("/overview", response_model=Overview)
async def overview(db: AsyncSession = Depends(get_db)):
    """Everything the web app's admin dashboard and analytics pages show (camelCase)."""
    return await service.get_overview(db)


@router.get("/users", response_model=AdminUserPage)
async def users(
    q: str | None = Query(None, max_length=100),
    status: str | None = Query(None, pattern="^(active|deactivated)$"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    return await service.list_users(db, q, status, limit, offset)


@router.patch("/users/{user_id}", response_model=AdminUser)
async def update_user_status(
    user_id: str,
    payload: UserStatusUpdate,
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    user = await service.set_user_active(db, admin, user_id, payload.is_active)
    return (await service.enrich_users(db, [user]))[0]


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: str,
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    await service.delete_user(db, admin, user_id)
    return None


@router.get("/questions", response_model=AdminQuestionPage)
async def questions(
    q: str | None = Query(None, max_length=100),
    topic: str | None = Query(None, max_length=50),
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    return await service.list_questions(db, q, topic, limit, offset)


@router.get("/documents", response_model=AdminDocumentPage)
async def documents(
    q: str | None = Query(None, max_length=100),
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    return await service.list_documents(db, q, limit, offset)


@router.get("/system", response_model=SystemStatus)
async def system(db: AsyncSession = Depends(get_db)):
    return await service.get_system(db)


@router.get("/audit", response_model=AuditPage)
async def audit(
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    return await service.list_audit(db, limit, offset)
