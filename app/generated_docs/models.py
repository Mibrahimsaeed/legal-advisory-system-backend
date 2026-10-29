import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class GeneratedDocument(Base):
    """A PDF or Word file the app made for the user (a saved answer,
    a whole conversation, or case law). Stored next to uploaded files."""

    __tablename__ = "generated_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True, nullable=False)

    kind: Mapped[str] = mapped_column(String(20), nullable=False)  # answer | conversation | case_law
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    file_format: Mapped[str] = mapped_column(String(10), nullable=False)  # pdf | docx
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_key: Mapped[str] = mapped_column(String(255), nullable=False)

    # Where it came from. Plain columns (no foreign key) so the document
    # survives if the user later deletes the chat.
    conversation_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    source_title: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
