"""
FastAPI dependencies — auth, DB session, RBAC.

No Redis. Sessions are backed by the Postgres `sessions` table via
SessionService (in-memory + DB fallback).
"""
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db
from app.models.rbac import Permission, Role, RolePermission, UserRole
from app.models.user import User
from app.services.session_service import SessionService

_settings = get_settings()

# ----------------------------------------------------------------
# Core dependencies
# ----------------------------------------------------------------
DBSession = Annotated[AsyncSession, Depends(get_db)]


def get_session_service() -> SessionService:
    """Session service — no external dependency."""
    return SessionService()


SessionServiceDep = Annotated[SessionService, Depends(get_session_service)]


# ----------------------------------------------------------------
# Token extraction
# ----------------------------------------------------------------
def _extract_token(request: Request) -> str | None:
    """Look for the session token in the cookie, then in the Authorization header."""
    token = request.cookies.get(_settings.session_cookie_name)
    if token:
        return token
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return None


# ----------------------------------------------------------------
# Current user
# ----------------------------------------------------------------
async def get_current_user(
    request: Request,
    db: DBSession,
    sessions: SessionServiceDep,
) -> User:
    token = _extract_token(request)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")

    payload = await sessions.validate_and_touch(token)
    if not payload:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session invalid or expired")

    try:
        user_id = UUID(payload["user_id"])
    except (KeyError, ValueError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Malformed session")

    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account unavailable")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


# ----------------------------------------------------------------
# RBAC helpers
# ----------------------------------------------------------------
async def get_user_permissions(db: AsyncSession, user_id: UUID) -> set[str]:
    rows = (
        await db.execute(
            select(Permission.key)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .join(Role, Role.id == RolePermission.role_id)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user_id)
        )
    ).scalars().all()
    return set(rows)


async def get_user_roles(db: AsyncSession, user_id: UUID) -> set[str]:
    rows = (
        await db.execute(
            select(Role.name)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user_id)
        )
    ).scalars().all()
    return set(rows)


def require_permissions(*required: str):
    """Route guard: caller must possess every listed permission key."""

    async def _guard(user: CurrentUser, db: DBSession) -> User:
        if not required:
            return user
        perms = await get_user_permissions(db, user.id)
        missing = [p for p in required if p not in perms]
        if missing:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"Missing required permission(s): {', '.join(missing)}",
            )
        return user

    return _guard


def require_roles(*required: str):
    """Route guard: caller must possess at least one of the listed roles."""

    async def _guard(user: CurrentUser, db: DBSession) -> User:
        if not required:
            return user
        roles = await get_user_roles(db, user.id)
        if not roles & set(required):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"Requires one of role(s): {', '.join(required)}",
            )
        return user

    return _guard