"""
Content CMS — Curriculum hierarchy CRUD.

Write routes require:
  - content.create  (create + update)
  - content.publish (publish/unpublish)
  - content.delete  (soft-delete)

Read routes:
  - GET list/detail: any authenticated user; students only see published items.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, DBSession, require_permissions
from app.models.curriculum import Course, Curriculum, Grade, Lesson, Subject, Unit
from app.schemas.content import (
    CourseCreate,
    CoursePublic,
    CourseUpdate,
    CurriculumCreate,
    CurriculumPublic,
    CurriculumUpdate,
    GradeCreate,
    GradePublic,
    GradeUpdate,
    LessonCreate,
    LessonPublic,
    LessonUpdate,
    ReorderRequest,
    SubjectCreate,
    SubjectPublic,
    SubjectUpdate,
    UnitCreate,
    UnitPublic,
    UnitUpdate,
)
from app.services import content_service as cs

router = APIRouter(prefix="/content", tags=["content"])

# ==================================================================
# Curricula
# ==================================================================
@router.get("/curricula", response_model=list[CurriculumPublic])
async def list_curricula(
    db: DBSession,
    _user: CurrentUser,
    only_active: bool = Query(default=True),
) -> list[CurriculumPublic]:
    stmt = select(Curriculum).where(Curriculum.deleted_at.is_(None))
    if only_active:
        stmt = stmt.where(Curriculum.is_active.is_(True))
    rows = (await db.execute(stmt.order_by(Curriculum.name))).scalars().all()
    return [CurriculumPublic.model_validate(r) for r in rows]


@router.post(
    "/curricula",
    response_model=CurriculumPublic,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions("content.create"))],
)
async def create_curriculum(payload: CurriculumCreate, db: DBSession) -> CurriculumPublic:
    await cs.ensure_unique_name(db, Curriculum, "name", payload.name)
    obj = Curriculum(**payload.model_dump())
    db.add(obj)
    await db.flush()
    return CurriculumPublic.model_validate(obj)


@router.get("/curricula/{curriculum_id}", response_model=CurriculumPublic)
async def get_curriculum(curriculum_id: UUID, db: DBSession, _user: CurrentUser) -> CurriculumPublic:
    obj = await cs.get_or_404(db, Curriculum, curriculum_id)
    return CurriculumPublic.model_validate(obj)


@router.patch(
    "/curricula/{curriculum_id}",
    response_model=CurriculumPublic,
    dependencies=[Depends(require_permissions("content.create"))],
)
async def update_curriculum(
    curriculum_id: UUID, payload: CurriculumUpdate, db: DBSession
) -> CurriculumPublic:
    obj = await cs.get_or_404(db, Curriculum, curriculum_id)
    data = payload.model_dump(exclude_unset=True)
    if "name" in data and data["name"] != obj.name:
        await cs.ensure_unique_name(db, Curriculum, "name", data["name"], exclude_id=obj.id)
    await cs.apply_update(db, obj, data)
    return CurriculumPublic.model_validate(obj)


@router.delete(
    "/curricula/{curriculum_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permissions("content.delete"))],
)
async def delete_curriculum(curriculum_id: UUID, db: DBSession) -> None:
    obj = await cs.get_or_404(db, Curriculum, curriculum_id)
    await cs.soft_delete(db, obj)


# ==================================================================
# Grades
# ==================================================================
@router.get("/grades", response_model=list[GradePublic])
async def list_grades(
    db: DBSession,
    _user: CurrentUser,
    curriculum_id: UUID | None = Query(default=None),
) -> list[GradePublic]:
    stmt = select(Grade).where(Grade.deleted_at.is_(None))
    if curriculum_id is not None:
        stmt = stmt.where(Grade.curriculum_id == curriculum_id)
    rows = (await db.execute(stmt.order_by(Grade.level_number))).scalars().all()
    return [GradePublic.model_validate(r) for r in rows]


@router.post(
    "/grades",
    response_model=GradePublic,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions("content.create"))],
)
async def create_grade(payload: GradeCreate, db: DBSession) -> GradePublic:
    await cs.get_or_404(db, Curriculum, payload.curriculum_id)
    obj = Grade(**payload.model_dump())
    db.add(obj)
    await db.flush()
    return GradePublic.model_validate(obj)


@router.get("/grades/{grade_id}", response_model=GradePublic)
async def get_grade(grade_id: UUID, db: DBSession, _user: CurrentUser) -> GradePublic:
    obj = await cs.get_or_404(db, Grade, grade_id)
    return GradePublic.model_validate(obj)


@router.patch(
    "/grades/{grade_id}",
    response_model=GradePublic,
    dependencies=[Depends(require_permissions("content.create"))],
)
async def update_grade(grade_id: UUID, payload: GradeUpdate, db: DBSession) -> GradePublic:
    obj = await cs.get_or_404(db, Grade, grade_id)
    await cs.apply_update(db, obj, payload.model_dump(exclude_unset=True))
    return GradePublic.model_validate(obj)


@router.delete(
    "/grades/{grade_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permissions("content.delete"))],
)
async def delete_grade(grade_id: UUID, db: DBSession) -> None:
    obj = await cs.get_or_404(db, Grade, grade_id)
    await cs.soft_delete(db, obj)


# ==================================================================
# Subjects
# ==================================================================
@router.get("/subjects", response_model=list[SubjectPublic])
async def list_subjects(
    db: DBSession,
    _user: CurrentUser,
    grade_id: UUID | None = Query(default=None),
) -> list[SubjectPublic]:
    stmt = select(Subject).where(Subject.deleted_at.is_(None))
    if grade_id is not None:
        stmt = stmt.where(Subject.grade_id == grade_id)
    rows = (await db.execute(stmt.order_by(Subject.name))).scalars().all()
    return [SubjectPublic.model_validate(r) for r in rows]


@router.post(
    "/subjects",
    response_model=SubjectPublic,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions("content.create"))],
)
async def create_subject(payload: SubjectCreate, db: DBSession) -> SubjectPublic:
    await cs.get_or_404(db, Grade, payload.grade_id)
    obj = Subject(**payload.model_dump())
    db.add(obj)
    await db.flush()
    return SubjectPublic.model_validate(obj)


@router.get("/subjects/{subject_id}", response_model=SubjectPublic)
async def get_subject(subject_id: UUID, db: DBSession, _user: CurrentUser) -> SubjectPublic:
    obj = await cs.get_or_404(db, Subject, subject_id)
    return SubjectPublic.model_validate(obj)


@router.patch(
    "/subjects/{subject_id}",
    response_model=SubjectPublic,
    dependencies=[Depends(require_permissions("content.create"))],
)
async def update_subject(
    subject_id: UUID, payload: SubjectUpdate, db: DBSession
) -> SubjectPublic:
    obj = await cs.get_or_404(db, Subject, subject_id)
    await cs.apply_update(db, obj, payload.model_dump(exclude_unset=True))
    return SubjectPublic.model_validate(obj)


@router.delete(
    "/subjects/{subject_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permissions("content.delete"))],
)
async def delete_subject(subject_id: UUID, db: DBSession) -> None:
    obj = await cs.get_or_404(db, Subject, subject_id)
    await cs.soft_delete(db, obj)


# ==================================================================
# Courses
# ==================================================================
@router.get("/courses", response_model=list[CoursePublic])
async def list_courses(
    db: DBSession,
    _user: CurrentUser,
    subject_id: UUID | None = Query(default=None),
    include_unpublished: bool = Query(default=False),
) -> list[CoursePublic]:
    stmt = select(Course).where(Course.deleted_at.is_(None))
    if subject_id is not None:
        stmt = stmt.where(Course.subject_id == subject_id)
    if not include_unpublished:
        stmt = stmt.where(Course.is_published.is_(True))
    rows = (await db.execute(stmt.order_by(Course.title))).scalars().all()
    return [CoursePublic.model_validate(r) for r in rows]


@router.post(
    "/courses",
    response_model=CoursePublic,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions("content.create"))],
)
async def create_course(payload: CourseCreate, db: DBSession) -> CoursePublic:
    await cs.get_or_404(db, Subject, payload.subject_id)
    obj = Course(**payload.model_dump())
    db.add(obj)
    await db.flush()
    return CoursePublic.model_validate(obj)


@router.get("/courses/{course_id}", response_model=CoursePublic)
async def get_course(course_id: UUID, db: DBSession, _user: CurrentUser) -> CoursePublic:
    obj = await cs.get_or_404(db, Course, course_id)
    return CoursePublic.model_validate(obj)


@router.patch(
    "/courses/{course_id}",
    response_model=CoursePublic,
    dependencies=[Depends(require_permissions("content.create"))],
)
async def update_course(course_id: UUID, payload: CourseUpdate, db: DBSession) -> CoursePublic:
    obj = await cs.get_or_404(db, Course, course_id)
    await cs.apply_update(db, obj, payload.model_dump(exclude_unset=True))
    return CoursePublic.model_validate(obj)


@router.delete(
    "/courses/{course_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permissions("content.delete"))],
)
async def delete_course(course_id: UUID, db: DBSession) -> None:
    obj = await cs.get_or_404(db, Course, course_id)
    await cs.soft_delete(db, obj)


@router.post(
    "/courses/{course_id}/publish",
    response_model=CoursePublic,
    dependencies=[Depends(require_permissions("content.publish"))],
)
async def publish_course(course_id: UUID, db: DBSession) -> CoursePublic:
    obj = await cs.get_or_404(db, Course, course_id)
    obj.is_published = True
    await db.flush()
    return CoursePublic.model_validate(obj)


@router.post(
    "/courses/{course_id}/unpublish",
    response_model=CoursePublic,
    dependencies=[Depends(require_permissions("content.publish"))],
)
async def unpublish_course(course_id: UUID, db: DBSession) -> CoursePublic:
    obj = await cs.get_or_404(db, Course, course_id)
    obj.is_published = False
    await db.flush()
    return CoursePublic.model_validate(obj)


# ==================================================================
# Units
# ==================================================================
@router.get("/units", response_model=list[UnitPublic])
async def list_units(
    db: DBSession,
    _user: CurrentUser,
    course_id: UUID | None = Query(default=None),
) -> list[UnitPublic]:
    stmt = select(Unit).where(Unit.deleted_at.is_(None))
    if course_id is not None:
        stmt = stmt.where(Unit.course_id == course_id)
    rows = (await db.execute(stmt.order_by(Unit.order_index))).scalars().all()
    return [UnitPublic.model_validate(r) for r in rows]


@router.post(
    "/units",
    response_model=UnitPublic,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions("content.create"))],
)
async def create_unit(payload: UnitCreate, db: DBSession) -> UnitPublic:
    await cs.get_or_404(db, Course, payload.course_id)
    obj = Unit(**payload.model_dump())
    db.add(obj)
    await db.flush()
    return UnitPublic.model_validate(obj)


@router.get("/units/{unit_id}", response_model=UnitPublic)
async def get_unit(unit_id: UUID, db: DBSession, _user: CurrentUser) -> UnitPublic:
    obj = await cs.get_or_404(db, Unit, unit_id)
    return UnitPublic.model_validate(obj)


@router.patch(
    "/units/{unit_id}",
    response_model=UnitPublic,
    dependencies=[Depends(require_permissions("content.create"))],
)
async def update_unit(unit_id: UUID, payload: UnitUpdate, db: DBSession) -> UnitPublic:
    obj = await cs.get_or_404(db, Unit, unit_id)
    await cs.apply_update(db, obj, payload.model_dump(exclude_unset=True))
    return UnitPublic.model_validate(obj)


@router.delete(
    "/units/{unit_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permissions("content.delete"))],
)
async def delete_unit(unit_id: UUID, db: DBSession) -> None:
    obj = await cs.get_or_404(db, Unit, unit_id)
    await cs.soft_delete(db, obj)


@router.post(
    "/courses/{course_id}/units/reorder",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permissions("content.create"))],
)
async def reorder_units(course_id: UUID, payload: ReorderRequest, db: DBSession) -> None:
    await cs.get_or_404(db, Course, course_id)
    rows = (
        await db.execute(
            select(Unit).where(Unit.course_id == course_id, Unit.deleted_at.is_(None))
        )
    ).scalars().all()
    await cs.reorder_items(db, rows, payload.ids)


# ==================================================================
# Lessons
# ==================================================================
@router.get("/lessons", response_model=list[LessonPublic])
async def list_lessons(
    db: DBSession,
    _user: CurrentUser,
    unit_id: UUID | None = Query(default=None),
    include_unpublished: bool = Query(default=False),
) -> list[LessonPublic]:
    stmt = select(Lesson).where(Lesson.deleted_at.is_(None))
    if unit_id is not None:
        stmt = stmt.where(Lesson.unit_id == unit_id)
    if not include_unpublished:
        stmt = stmt.where(Lesson.is_published.is_(True))
    rows = (await db.execute(stmt.order_by(Lesson.order_index))).scalars().all()
    return [LessonPublic.model_validate(r) for r in rows]


@router.post(
    "/lessons",
    response_model=LessonPublic,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions("content.create"))],
)
async def create_lesson(payload: LessonCreate, db: DBSession) -> LessonPublic:
    await cs.get_or_404(db, Unit, payload.unit_id)
    obj = Lesson(**payload.model_dump())
    db.add(obj)
    await db.flush()
    return LessonPublic.model_validate(obj)


@router.get("/lessons/{lesson_id}", response_model=LessonPublic)
async def get_lesson(lesson_id: UUID, db: DBSession, _user: CurrentUser) -> LessonPublic:
    obj = await cs.get_or_404(db, Lesson, lesson_id)
    return LessonPublic.model_validate(obj)


@router.patch(
    "/lessons/{lesson_id}",
    response_model=LessonPublic,
    dependencies=[Depends(require_permissions("content.create"))],
)
async def update_lesson(
    lesson_id: UUID, payload: LessonUpdate, db: DBSession
) -> LessonPublic:
    obj = await cs.get_or_404(db, Lesson, lesson_id)
    await cs.apply_update(db, obj, payload.model_dump(exclude_unset=True))
    return LessonPublic.model_validate(obj)


@router.delete(
    "/lessons/{lesson_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permissions("content.delete"))],
)
async def delete_lesson(lesson_id: UUID, db: DBSession) -> None:
    obj = await cs.get_or_404(db, Lesson, lesson_id)
    await cs.soft_delete(db, obj)


@router.post(
    "/lessons/{lesson_id}/publish",
    response_model=LessonPublic,
    dependencies=[Depends(require_permissions("content.publish"))],
)
async def publish_lesson(lesson_id: UUID, db: DBSession) -> LessonPublic:
    obj = await cs.get_or_404(db, Lesson, lesson_id)
    obj.is_published = True
    await db.flush()
    return LessonPublic.model_validate(obj)


@router.post(
    "/lessons/{lesson_id}/unpublish",
    response_model=LessonPublic,
    dependencies=[Depends(require_permissions("content.publish"))],
)
async def unpublish_lesson(lesson_id: UUID, db: DBSession) -> LessonPublic:
    obj = await cs.get_or_404(db, Lesson, lesson_id)
    obj.is_published = False
    await db.flush()
    return LessonPublic.model_validate(obj)


@router.post(
    "/units/{unit_id}/lessons/reorder",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permissions("content.create"))],
)
async def reorder_lessons(unit_id: UUID, payload: ReorderRequest, db: DBSession) -> None:
    await cs.get_or_404(db, Unit, unit_id)
    rows = (
        await db.execute(
            select(Lesson).where(Lesson.unit_id == unit_id, Lesson.deleted_at.is_(None))
        )
    ).scalars().all()
    await cs.reorder_items(db, rows, payload.ids)