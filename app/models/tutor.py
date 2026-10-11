"""
Tutor profile + CV.
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPKMixin
from app.db.types import GUID

TUTOR_STATUSES = ("draft", "pending", "approved", "rejected", "suspended")


class TutorProfile(Base, UUIDPKMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "tutor_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    headline: Mapped[str | None] = mapped_column(String(200))
    bio: Mapped[str | None] = mapped_column(Text)

    phone: Mapped[str | None] = mapped_column(String(32))
    whatsapp: Mapped[str | None] = mapped_column(String(32))
    linkedin_url: Mapped[str | None] = mapped_column(String(500))
    website_url: Mapped[str | None] = mapped_column(String(500))

    city: Mapped[str | None] = mapped_column(String(100))
    country: Mapped[str | None] = mapped_column(String(2))

    subjects: Mapped[list | None] = mapped_column(JSON)
    grade_levels: Mapped[list | None] = mapped_column(JSON)
    languages: Mapped[list | None] = mapped_column(JSON)
    teaching_mode: Mapped[str | None] = mapped_column(String(20))

    years_experience: Mapped[int | None] = mapped_column(Integer)
    hourly_rate_usd: Mapped[float | None] = mapped_column(Numeric(10, 2))

    cv_file_key: Mapped[str | None] = mapped_column(String(500))
    cv_file_name: Mapped[str | None] = mapped_column(String(255))
    cv_file_size: Mapped[int | None] = mapped_column(Integer)
    cv_uploaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    education: Mapped[list | None] = mapped_column(JSON)
    experience: Mapped[list | None] = mapped_column(JSON)
    certifications: Mapped[list | None] = mapped_column(JSON)

    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL")
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text)

    is_public: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


Index("ix_tutor_profiles_status", TutorProfile.status)
Index("ix_tutor_profiles_country", TutorProfile.country)
Index("ix_tutor_profiles_user", TutorProfile.user_id)