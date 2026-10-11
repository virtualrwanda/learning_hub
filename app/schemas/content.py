from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ==================================================================
# Curricula
# ==================================================================
class CurriculumCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None
    is_active: bool = True


class CurriculumUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None
    is_active: bool | None = None


class CurriculumPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    description: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


# ==================================================================
# Grades
# ==================================================================
class GradeCreate(BaseModel):
    curriculum_id: UUID
    level_number: int = Field(ge=1, le=12)
    display_name: str = Field(min_length=1, max_length=50)
    is_active: bool = True


class GradeUpdate(BaseModel):
    level_number: int | None = Field(default=None, ge=1, le=12)
    display_name: str | None = Field(default=None, min_length=1, max_length=50)
    is_active: bool | None = None


class GradePublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    curriculum_id: UUID
    level_number: int
    display_name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


# ==================================================================
# Subjects
# ==================================================================
class SubjectCreate(BaseModel):
    grade_id: UUID
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None


class SubjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None


class SubjectPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    grade_id: UUID
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime


# ==================================================================
# Courses
# ==================================================================
class CourseCreate(BaseModel):
    subject_id: UUID
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    thumbnail_url: str | None = Field(default=None, max_length=500)
    is_free: bool = False
    is_published: bool = False


class CourseUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    thumbnail_url: str | None = Field(default=None, max_length=500)
    is_free: bool | None = None
    is_published: bool | None = None


class CoursePublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    subject_id: UUID
    title: str
    description: str | None
    thumbnail_url: str | None
    is_free: bool
    is_published: bool
    created_at: datetime
    updated_at: datetime


# ==================================================================
# Units
# ==================================================================
class UnitCreate(BaseModel):
    course_id: UUID
    title: str = Field(min_length=1, max_length=200)
    order_index: int = Field(default=0, ge=0)


class UnitUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    order_index: int | None = Field(default=None, ge=0)


class UnitPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    course_id: UUID
    title: str
    order_index: int
    created_at: datetime
    updated_at: datetime


# ==================================================================
# Lessons
# ==================================================================
class LessonCreate(BaseModel):
    unit_id: UUID
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    learning_objectives: str | None = None
    order_index: int = Field(default=0, ge=0)
    is_free: bool = False
    is_published: bool = False


class LessonUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    learning_objectives: str | None = None
    order_index: int | None = Field(default=None, ge=0)
    is_free: bool | None = None
    is_published: bool | None = None


class LessonPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    unit_id: UUID
    title: str
    description: str | None
    learning_objectives: str | None
    order_index: int
    is_free: bool
    is_published: bool
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ReorderRequest(BaseModel):
    """Reorder a list of items by their IDs. IDs not in the list are untouched."""

    ids: list[UUID] = Field(min_length=1)