from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# app/schemas/user.py
class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    email: EmailStr
    first_name: str
    last_name: str
    school_name: str | None
    current_grade_id: UUID | None
    country: str | None
    status: str
    email_verified_at: datetime | None
    created_at: datetime | None = None     # ← make optional


class UserUpdateSelf(BaseModel):
    """Fields a user may update on their own profile."""

    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    school_name: str | None = Field(default=None, max_length=255)
    grade_id: UUID | None = None
    phone: str | None = Field(default=None, max_length=32)
    