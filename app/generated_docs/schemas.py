from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

FileFormat = Literal["pdf", "docx"]


class GenerateFromChatRequest(BaseModel):
    source: Literal["answer", "conversation"]
    conversation_id: str
    message_id: str | None = None  # required when source == "answer"
    format: FileFormat

    @model_validator(mode="after")
    def _answer_needs_message(self):
        if self.source == "answer" and not self.message_id:
            raise ValueError("message_id is required to save a single answer")
        return self


class CaseLawRequest(BaseModel):
    query: str = Field(min_length=2, max_length=300)
    format: FileFormat


class GeneratedDocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    kind: str
    title: str
    file_format: str
    filename: str
    size_bytes: int
    conversation_id: str | None
    source_title: str | None
    created_at: datetime


class CaseLawStatus(BaseModel):
    available: bool
    cases: int
