from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UserProfile(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    full_name: str | None = None
    is_active: bool
    created_at: datetime


class UserUpdate(BaseModel):
    full_name: str | None = None
