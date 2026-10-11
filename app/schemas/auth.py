from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


# Roles a user can self-register as.
# Admin and content_manager are intentionally excluded — invite-only.
SELF_REGISTRABLE_ROLES = ("student", "tutor", "parent")


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    school_name: str | None = Field(default=None, max_length=255)
    grade_id: UUID | None = None
    country: str | None = Field(default=None, min_length=2, max_length=2)
    # Default: student. Tutors and parents opt-in explicitly.
    role: str = Field(default="student")


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class MessageResponse(BaseModel):
    message: str