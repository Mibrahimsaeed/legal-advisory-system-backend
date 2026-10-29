from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.chat.answer import ArchetypeId, LegalAnswer, LegalDomain


class ConversationCreate(BaseModel):
    # Optional: the web app creates the id up front so it can open the chat
    # straight away. Must be a UUID that is not already in use.
    id: UUID | None = None
    title: str | None = Field(default=None, max_length=255)
    domain: LegalDomain = "general"
    archetype: ArchetypeId | None = None


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    domain: str
    archetype: str | None = None
    created_at: datetime
    updated_at: datetime


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    conversation_id: str
    role: str
    content: str
    answer: LegalAnswer | None = None
    created_at: datetime


class ConversationDetail(ConversationOut):
    """A conversation together with all its messages (used for the history list)."""
    messages: list[MessageOut]
