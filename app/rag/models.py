import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class RagDocument(Base):
    """A legal source (statute, act, ordinance, regulation) an admin submitted
    for the AI knowledge base. The row id doubles as the ingestion job id."""

    __tablename__ = "rag_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    document_type: Mapped[str] = mapped_column(String(20), nullable=False)  # statute|act|ordinance|regulation
    jurisdiction: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    year: Mapped[str] = mapped_column(String(10), nullable=False, default="")
    category: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    source: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    content: Mapped[str | None] = mapped_column(Text, nullable=True)  # pasted text or text extracted from the file

    file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    storage_key: Mapped[str | None] = mapped_column(String(255), nullable=True)

    status: Mapped[str] = mapped_column(String(20), default="submitted", index=True)  # submitted|processing|completed|failed
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    submitted_by: Mapped[str] = mapped_column(String(36), nullable=False)  # admin user id (no FK: survives account changes)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
