from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password
from app.models.rbac import Role, UserRole
from app.models.tutor import TutorProfile
from app.models.user import User
from app.schemas.auth import SELF_REGISTRABLE_ROLES


class AuthService:
    @staticmethod
    async def register(
        db: AsyncSession,
        *,
        email: str,
        password: str,
        first_name: str,
        last_name: str,
        school_name: str | None = None,
        grade_id=None,
        country: str | None = None,
        role: str = "student",
    ) -> User:
        email = email.lower().strip()

        if role not in SELF_REGISTRABLE_ROLES:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"Role '{role}' cannot be self-registered. "
                f"Allowed: {', '.join(SELF_REGISTRABLE_ROLES)}",
            )

        existing = (
            await db.execute(select(User).where(User.email == email))
        ).scalar_one_or_none()
        if existing:
            raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")

        user = User(
            email=email,
            password_hash=hash_password(password),
            first_name=first_name.strip(),
            last_name=last_name.strip(),
            school_name=school_name,
            current_grade_id=grade_id,
            country=country,
            status="active",
        )
        db.add(user)
        await db.flush()

        # Attach the requested role
        requested_role = (
            await db.execute(select(Role).where(Role.name == role))
        ).scalar_one_or_none()
        if requested_role is None:
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                f"Role '{role}' missing from database — run seed_rbac",
            )
        db.add(UserRole(user_id=user.id, role_id=requested_role.id))

        # Tutors get an empty tutor profile created automatically
        if role == "tutor":
            db.add(TutorProfile(user_id=user.id, status="draft"))

        return user

    @staticmethod
    async def authenticate(db: AsyncSession, *, email: str, password: str) -> User:
        email = email.lower().strip()
        user = (
            await db.execute(select(User).where(User.email == email))
        ).scalar_one_or_none()
        if not user or not verify_password(password, user.password_hash):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
        if not user.is_active:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Account suspended")
        return user

    @staticmethod
    async def change_password(
        db: AsyncSession, user: User, current: str, new: str
    ) -> None:
        if not verify_password(current, user.password_hash):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "Current password is incorrect"
            )
        user.password_hash = hash_password(new)
        await db.flush()