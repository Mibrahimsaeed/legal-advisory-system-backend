from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserProfile(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    full_name: str | None = None
    is_active: bool
    is_admin: bool = False
    created_at: datetime


class UserUpdate(BaseModel):
    full_name: str | None = None


class DeleteAccountRequest(BaseModel):
    """Deleting an account needs the email and password again, not just a
    logged-in session, so a borrowed phone or a stray tap can't do it."""
    email: str
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class ChangeEmailRequest(BaseModel):
    new_email: EmailStr
    password: str


class ConfirmEmailChangeRequest(BaseModel):
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class MessageResponse(BaseModel):
    message: str
