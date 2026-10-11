"""
Tutor profile + CV routes.

- Tutor self-service: /tutors/me and /tutors/me/cv
- Public:             /tutors and /tutors/{id}
- Admin:              /tutors/admin/*
"""
from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile, status
from fastapi.responses import FileResponse

from app.core.deps import CurrentUser, DBSession, require_permissions
from app.schemas.tutor import (
    TutorProfileCreate,
    TutorProfileListItem,
    TutorProfilePublic,
    TutorProfileUpdate,
    TutorRejectRequest,
    TutorVisibilityToggle,
)
from app.services.tutor_service import TutorService

router = APIRouter(prefix="/tutors", tags=["tutors"])


# ==================================================================
# Tutor self-service
# ==================================================================
@router.get("/me", response_model=TutorProfilePublic)
async def my_profile(db: DBSession, user: CurrentUser) -> TutorProfilePublic:
    profile = await TutorService.get_or_create_for_user(db, user.id)
    return TutorProfilePublic.model_validate(profile)


@router.patch("/me", response_model=TutorProfilePublic)
async def update_my_profile(
    payload: TutorProfileUpdate,
    db: DBSession,
    user: CurrentUser,
) -> TutorProfilePublic:
    profile = await TutorService.get_or_create_for_user(db, user.id)
    if profile.status in ("pending", "approved"):
        # Allow edits, they just won't take effect publicly until re-approved
        # (or you can lock it — product decision)
        pass
    updated = await TutorService.update_profile(
        db, profile, payload.model_dump(exclude_unset=True)
    )
    return TutorProfilePublic.model_validate(updated)


@router.post("/me/submit", response_model=TutorProfilePublic)
async def submit_my_profile(db: DBSession, user: CurrentUser) -> TutorProfilePublic:
    profile = await TutorService.get_or_create_for_user(db, user.id)
    updated = await TutorService.submit_for_approval(db, profile)
    return TutorProfilePublic.model_validate(updated)


@router.post("/me/cv", response_model=TutorProfilePublic)
async def upload_my_cv(
    db: DBSession,
    user: CurrentUser,
    file: UploadFile = File(...),
) -> TutorProfilePublic:
    profile = await TutorService.get_or_create_for_user(db, user.id)
    updated = await TutorService.upload_cv(db, profile, file)
    return TutorProfilePublic.model_validate(updated)


@router.get("/me/cv")
async def download_my_cv(db: DBSession, user: CurrentUser) -> FileResponse:
    profile = await TutorService.get_or_create_for_user(db, user.id)
    path = TutorService.cv_path(profile)
    return FileResponse(
        path,
        media_type="application/octet-stream",
        filename=profile.cv_file_name or "cv",
    )


# ==================================================================
# Public
# ==================================================================
@router.get("", response_model=list[TutorProfileListItem])
async def list_tutors(
    db: DBSession,
    subject: str | None = Query(default=None),
    country: str | None = Query(default=None, min_length=2, max_length=2),
    limit: int = Query(default=50, le=200),
    offset: int = 0,
) -> list[TutorProfileListItem]:
    rows = await TutorService.public_list(
        db, subject=subject, country=country, limit=limit, offset=offset
    )
    return [TutorProfileListItem.model_validate(r) for r in rows]


@router.get("/{profile_id}", response_model=TutorProfilePublic)
async def get_tutor(profile_id: UUID, db: DBSession) -> TutorProfilePublic:
    profile = await TutorService.public_get(db, profile_id)
    return TutorProfilePublic.model_validate(profile)


# ==================================================================
# Admin
# ==================================================================
@router.get(
    "/admin/all",
    response_model=list[TutorProfilePublic],
    dependencies=[Depends(require_permissions("tutor.approve"))],
)
async def admin_list(
    db: DBSession,
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, le=500),
    offset: int = 0,
) -> list[TutorProfilePublic]:
    rows = await TutorService.admin_list(
        db, status_filter=status_filter, limit=limit, offset=offset
    )
    return [TutorProfilePublic.model_validate(r) for r in rows]


@router.post(
    "/admin/{profile_id}/approve",
    response_model=TutorProfilePublic,
    dependencies=[Depends(require_permissions("tutor.approve"))],
)
async def admin_approve(
    profile_id: UUID, request: Request, db: DBSession, user: CurrentUser
) -> TutorProfilePublic:
    profile = await TutorService.admin_approve(
        db,
        actor_user_id=user.id,
        profile_id=profile_id,
        ip_address=request.client.host if request.client else None,
    )
    return TutorProfilePublic.model_validate(profile)


@router.post(
    "/admin/{profile_id}/reject",
    response_model=TutorProfilePublic,
    dependencies=[Depends(require_permissions("tutor.approve"))],
)
async def admin_reject(
    profile_id: UUID,
    payload: TutorRejectRequest,
    request: Request,
    db: DBSession,
    user: CurrentUser,
) -> TutorProfilePublic:
    profile = await TutorService.admin_reject(
        db,
        actor_user_id=user.id,
        profile_id=profile_id,
        reason=payload.reason,
        ip_address=request.client.host if request.client else None,
    )
    return TutorProfilePublic.model_validate(profile)


@router.post(
    "/admin/{profile_id}/visibility",
    response_model=TutorProfilePublic,
    dependencies=[Depends(require_permissions("tutor.approve"))],
)
async def admin_visibility(
    profile_id: UUID,
    payload: TutorVisibilityToggle,
    request: Request,
    db: DBSession,
    user: CurrentUser,
) -> TutorProfilePublic:
    profile = await TutorService.admin_set_visibility(
        db,
        actor_user_id=user.id,
        profile_id=profile_id,
        is_public=payload.is_public,
        ip_address=request.client.host if request.client else None,
    )
    return TutorProfilePublic.model_validate(profile)


@router.get(
    "/admin/{profile_id}/cv",
    dependencies=[Depends(require_permissions("tutor.approve"))],
)
async def admin_download_cv(profile_id: UUID, db: DBSession) -> FileResponse:
    profile = await TutorService._get(db, profile_id)
    path = TutorService.cv_path(profile)
    return FileResponse(
        path,
        media_type="application/octet-stream",
        filename=profile.cv_file_name or "cv",
    )