from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EducationEntry(BaseModel):
    degree: str = Field(min_length=1, max_length=200)
    institution: str = Field(min_length=1, max_length=200)
    year: int | None = Field(default=None, ge=1950, le=2100)
    details: str | None = None


class ExperienceEntry(BaseModel):
    role: str = Field(min_length=1, max_length=200)
    organization: str = Field(min_length=1, max_length=200)
    from_year: int | None = Field(default=None, ge=1950, le=2100)
    to_year: int | None = Field(default=None, ge=1950, le=2100)
    current: bool = False
    details: str | None = None


class CertificationEntry(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    issuer: str | None = None
    year: int | None = Field(default=None, ge=1950, le=2100)


class LanguageEntry(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    level: str = Field(pattern="^(basic|conversational|fluent|native)$")


class TutorProfileCreate(BaseModel):
    headline: str | None = Field(default=None, max_length=200)
    bio: str | None = None
    phone: str | None = Field(default=None, max_length=32)
    whatsapp: str | None = Field(default=None, max_length=32)
    linkedin_url: str | None = Field(default=None, max_length=500)
    website_url: str | None = Field(default=None, max_length=500)
    city: str | None = Field(default=None, max_length=100)
    country: str | None = Field(default=None, min_length=2, max_length=2)
    subjects: list[str] | None = None
    grade_levels: list[int] | None = None
    languages: list[LanguageEntry] | None = None
    teaching_mode: str | None = Field(default=None, pattern="^(online|in_person|both)$")
    years_experience: int | None = Field(default=None, ge=0, le=80)
    hourly_rate_usd: float | None = Field(default=None, ge=0)
    education: list[EducationEntry] | None = None
    experience: list[ExperienceEntry] | None = None
    certifications: list[CertificationEntry] | None = None


class TutorProfileUpdate(TutorProfileCreate):
    pass


class TutorProfilePublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    headline: str | None
    bio: str | None
    phone: str | None
    whatsapp: str | None
    linkedin_url: str | None
    website_url: str | None
    city: str | None
    country: str | None
    subjects: list | None
    grade_levels: list | None
    languages: list | None
    teaching_mode: str | None
    years_experience: int | None
    hourly_rate_usd: float | None

    cv_file_name: str | None
    cv_file_size: int | None
    cv_uploaded_at: datetime | None

    education: list | None
    experience: list | None
    certifications: list | None

    status: str
    submitted_at: datetime | None
    approved_at: datetime | None
    approved_by_user_id: UUID | None
    rejection_reason: str | None
    is_public: bool

    created_at: datetime
    updated_at: datetime


class TutorProfileListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    headline: str | None
    city: str | None
    country: str | None
    subjects: list | None
    grade_levels: list | None
    languages: list | None
    teaching_mode: str | None
    years_experience: int | None
    hourly_rate_usd: float | None
    approved_at: datetime | None


class TutorRejectRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class TutorVisibilityToggle(BaseModel):
    is_public: bool