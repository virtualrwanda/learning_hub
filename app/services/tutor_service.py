"""
Tutor profile + CV service.
"""
import os
import uuid as uuid_lib
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.tutor import TutorProfile
from app.services.audit_service import AuditService

# Storage root — override via env later
CV_STORAGE_DIR = Path("uploads") / "tutor_cvs"
CV_STORAGE_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_CV_EXTENSIONS = {".pdf", ".doc", ".docx"}
MAX_CV_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


class TutorService:
    # ------------------------------------------------------------------
    # Tutor-side
    # ------------------------------------------------------------------
    @staticmethod
    async def get_or_create_for_user(db: AsyncSession, user_id: UUID) -> TutorProfile:
        profile = (
            await db.execute(
                select(TutorProfile).where(
                    TutorProfile.user_id == user_id,
                    TutorProfile.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if profile is None:
            profile = TutorProfile(user_id=user_id, status="draft")
            db.add(profile)
            await db.flush()
        return profile

    @staticmethod
    async def update_profile(
        db: AsyncSession, profile: TutorProfile, payload: dict
    ) -> TutorProfile:
        # Convert Pydantic sub-models to plain dicts for JSON columns
        def _dump(v):
            if v is None:
                return None
            if isinstance(v, list):
                return [item.model_dump() if hasattr(item, "model_dump") else item for item in v]
            return v

        for field, value in payload.items():
            setattr(profile, field, _dump(value))
        await db.flush()
        return profile

    @staticmethod
    async def submit_for_approval(db: AsyncSession, profile: TutorProfile) -> TutorProfile:
        if profile.status == "approved":
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Already approved")
        if not profile.headline or not profile.bio:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Headline and bio are required before submission",
            )
        if not profile.cv_file_key:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "Upload a CV before submitting",
            )
        profile.status = "pending"
        profile.submitted_at = datetime.now(timezone.utc)
        profile.rejection_reason = None
        await db.flush()
        return profile

    @staticmethod
    async def upload_cv(
        db: AsyncSession, profile: TutorProfile, file: UploadFile
    ) -> TutorProfile:
        # Validate extension
        ext = os.path.splitext(file.filename or "")[1].lower()
        if ext not in ALLOWED_CV_EXTENSIONS:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"Unsupported file type. Allowed: {', '.join(sorted(ALLOWED_CV_EXTENSIONS))}",
            )

        # Read + validate size
        contents = await file.read()
        if len(contents) > MAX_CV_SIZE_BYTES:
            raise HTTPException(
                status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                f"CV exceeds {MAX_CV_SIZE_BYTES // (1024 * 1024)} MB limit",
            )
        if len(contents) == 0:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Empty file")

        # Simple magic-byte sanity check
        if ext == ".pdf" and not contents.startswith(b"%PDF"):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "File does not look like a PDF")

        # Save
        stored_name = f"{profile.user_id}_{uuid_lib.uuid4().hex}{ext}"
        dest = CV_STORAGE_DIR / stored_name
        dest.write_bytes(contents)

        # Remove old CV if any
        if profile.cv_file_key:
            old = Path(profile.cv_file_key)
            if old.exists() and old.parent == CV_STORAGE_DIR:
                try:
                    old.unlink()
                except OSError:
                    pass

        profile.cv_file_key = str(dest)
        profile.cv_file_name = file.filename
        profile.cv_file_size = len(contents)
        profile.cv_uploaded_at = datetime.now(timezone.utc)
        await db.flush()
        return profile

    @staticmethod
    def cv_path(profile: TutorProfile) -> Path:
        if not profile.cv_file_key:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "No CV uploaded")
        p = Path(profile.cv_file_key)
        if not p.exists():
            raise HTTPException(status.HTTP_404_NOT_FOUND, "CV file missing on server")
        return p

    # ------------------------------------------------------------------
    # Admin-side
    # ------------------------------------------------------------------
    @staticmethod
    async def admin_list(
        db: AsyncSession,
        *,
        status_filter: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[TutorProfile]:
        stmt = select(TutorProfile).where(TutorProfile.deleted_at.is_(None))
        if status_filter:
            stmt = stmt.where(TutorProfile.status == status_filter)
        stmt = stmt.order_by(TutorProfile.created_at.desc()).limit(limit).offset(offset)
        return (await db.execute(stmt)).scalars().all()

    @staticmethod
    async def admin_approve(
        db: AsyncSession,
        *,
        actor_user_id: UUID,
        profile_id: UUID,
        ip_address: str | None,
    ) -> TutorProfile:
        profile = await TutorService._get(db, profile_id)
        previous = {"status": profile.status, "is_public": profile.is_public}
        now = datetime.now(timezone.utc)
        profile.status = "approved"
        profile.approved_at = now
        profile.approved_by_user_id = actor_user_id
        profile.rejection_reason = None
        profile.is_public = True  # approved tutors are public by default
        await db.flush()

        await AuditService.log(
            db,
            actor_user_id=actor_user_id,
            action="tutor.approve",
            target_entity_type="tutor_profile",
            target_entity_id=profile.id,
            previous_value=previous,
            new_value={"status": profile.status, "is_public": profile.is_public},
            ip_address=ip_address,
        )
        return profile

    @staticmethod
    async def admin_reject(
        db: AsyncSession,
        *,
        actor_user_id: UUID,
        profile_id: UUID,
        reason: str,
        ip_address: str | None,
    ) -> TutorProfile:
        profile = await TutorService._get(db, profile_id)
        previous = {"status": profile.status}
        profile.status = "rejected"
        profile.rejection_reason = reason
        profile.is_public = False
        await db.flush()

        await AuditService.log(
            db,
            actor_user_id=actor_user_id,
            action="tutor.reject",
            target_entity_type="tutor_profile",
            target_entity_id=profile.id,
            previous_value=previous,
            new_value={"status": "rejected", "reason": reason},
            ip_address=ip_address,
        )
        return profile

    @staticmethod
    async def admin_set_visibility(
        db: AsyncSession,
        *,
        actor_user_id: UUID,
        profile_id: UUID,
        is_public: bool,
        ip_address: str | None,
    ) -> TutorProfile:
        profile = await TutorService._get(db, profile_id)
        previous = {"is_public": profile.is_public}
        profile.is_public = is_public
        await db.flush()

        await AuditService.log(
            db,
            actor_user_id=actor_user_id,
            action="tutor.visibility",
            target_entity_type="tutor_profile",
            target_entity_id=profile.id,
            previous_value=previous,
            new_value={"is_public": is_public},
            ip_address=ip_address,
        )
        return profile

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------
    @staticmethod
    async def public_list(
        db: AsyncSession,
        *,
        subject: str | None = None,
        country: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[TutorProfile]:
        stmt = (
            select(TutorProfile)
            .where(
                TutorProfile.deleted_at.is_(None),
                TutorProfile.status == "approved",
                TutorProfile.is_public.is_(True),
            )
            .order_by(TutorProfile.approved_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if country:
            stmt = stmt.where(TutorProfile.country == country)
        rows = (await db.execute(stmt)).scalars().all()
        if subject:
            # JSON contains — filter in Python since MySQL JSON path filter is fiddly
            rows = [r for r in rows if r.subjects and subject in r.subjects]
        return rows

    @staticmethod
    async def public_get(db: AsyncSession, profile_id: UUID) -> TutorProfile:
        profile = (
            await db.execute(
                select(TutorProfile).where(
                    TutorProfile.id == profile_id,
                    TutorProfile.deleted_at.is_(None),
                    TutorProfile.status == "approved",
                    TutorProfile.is_public.is_(True),
                )
            )
        ).scalar_one_or_none()
        if profile is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Tutor not found")
        return profile

    # ------------------------------------------------------------------
    @staticmethod
    async def _get(db: AsyncSession, profile_id: UUID) -> TutorProfile:
        profile = (
            await db.execute(
                select(TutorProfile).where(
                    TutorProfile.id == profile_id,
                    TutorProfile.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if profile is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Tutor profile not found")
        return profile