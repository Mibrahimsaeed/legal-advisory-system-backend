from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

RagDocumentType = Literal["statute", "act", "ordinance", "regulation"]


class RagSubmissionOut(BaseModel):
    job_id: str
    title: str
    document_type: str
    jurisdiction: str
    submitted_at: datetime


class RagJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    job_id: str
    status: str  # submitted | processing | completed | failed
    title: str
    document_type: str
    submitted_at: datetime
    completed_at: datetime | None = None
    error_message: str | None = None
