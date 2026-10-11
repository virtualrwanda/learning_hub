import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPKMixin
from app.db.types import GUID


class Curriculum(Base, UUIDPKMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "curricula"

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Grade(Base, UUIDPKMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "grades"

    curriculum_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("curricula.id", ondelete="CASCADE"), nullable=False
    )
    level_number: Mapped[int] = mapped_column(Integer, nullable=False)
    display_name: Mapped[str] = mapped_column(String(50), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (
        UniqueConstraint("curriculum_id", "level_number", name="uq_grade_curriculum_level"),
    )


class Subject(Base, UUIDPKMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "subjects"

    grade_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("grades.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)


class Course(Base, UUIDPKMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "courses"

    subject_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    thumbnail_url: Mapped[str | None] = mapped_column(String(500))
    is_free: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Unit(Base, UUIDPKMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "units"

    course_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class Lesson(Base, UUIDPKMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "lessons"

    unit_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("units.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    learning_objectives: Mapped[str | None] = mapped_column(Text)
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_free: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


Index("ix_courses_subject", Course.subject_id)
Index("ix_units_course_order", Unit.course_id, Unit.order_index)
Index("ix_lessons_unit_order", Lesson.unit_id, Lesson.order_index)