import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class Subscription(Base):
    """A user's current paid plan. No row (or an expired one) means the free plan."""

    __tablename__ = "subscriptions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), unique=True, nullable=False)
    plan_id: Mapped[str] = mapped_column(String(20), nullable=False)  # monthly | quarterly
    status: Mapped[str] = mapped_column(String(20), default="active")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)


class Payment(Base):
    """One confirmed payment. Kept even if the user is later deleted (revenue history),
    so user_id is a plain column rather than a foreign key."""

    __tablename__ = "payments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    plan_id: Mapped[str] = mapped_column(String(20), nullable=False)
    amount_pkr: Mapped[int] = mapped_column(Integer, nullable=False)
    reference: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class FreeUsage(Base):
    """Free-plan question counter. The window restarts FREE_REFRESH_HOURS after the limit is hit."""

    __tablename__ = "free_usage"

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), primary_key=True)
    used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    limit_reached_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
