"""
Admin + Super Admin routes.

Rules enforced here (blueprint Section 6):
  - Super Admin ONLY: settings.manage, role/permission management, payment
    provider configuration.
  - Admin: user management, subscription management, report viewing.
  - No admin can modify a Super Admin user account.
"""
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select

from app.core.deps import (
    CurrentUser,
    DBSession,
    get_user_permissions,
    require_permissions,
)
from app.models.audit import AuditLog
from app.models.rbac import Permission, Role, RolePermission, UserRole
from app.models.system_settings import SystemSetting
from app.models.user import User
from app.schemas.user import UserPublic
from app.services.audit_service import AuditService

router = APIRouter(prefix="/admin", tags=["admin"])


# ==================================================================
# System settings — SUPER ADMIN ONLY
# ==================================================================
@router.get(
    "/settings",
    dependencies=[Depends(require_permissions("settings.manage"))],
)
async def list_settings(db: DBSession) -> list[dict]:
    rows = (await db.execute(select(SystemSetting).order_by(SystemSetting.key))).scalars().all()
    return [
        {
            "key": r.key,
            "value": r.value,
            "description": r.description,
            "is_public": r.is_public,
        }
        for r in rows
    ]


@router.put(
    "/settings/{key}",
    dependencies=[Depends(require_permissions("settings.manage"))],
)
async def update_setting(
    key: str,
    payload: dict,
    request: Request,
    db: DBSession,
    user: CurrentUser,
) -> dict:
    if "value" not in payload:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "`value` is required")

    setting = (
        await db.execute(select(SystemSetting).where(SystemSetting.key == key))
    ).scalar_one_or_none()
    previous = setting.value if setting else None

    if setting is None:
        setting = SystemSetting(key=key, value=payload["value"], is_public=payload.get("is_public", False))
        db.add(setting)
    else:
        setting.value = payload["value"]
        if "is_public" in payload:
            setting.is_public = payload["is_public"]

    await db.flush()
    await AuditService.log(
        db,
        actor_user_id=user.id,
        action="settings.update",
        target_entity_type="system_setting",
        target_entity_id=setting.id,
        previous_value={"value": previous},
        new_value={"value": setting.value, "key": key},
        ip_address=request.client.host if request.client else None,
    )
    return {"key": setting.key, "value": setting.value, "is_public": setting.is_public}


# ==================================================================
# Users — admin with users.*
# ==================================================================
@router.get(
    "/users",
    response_model=list[UserPublic],
    dependencies=[Depends(require_permissions("users.view"))],
)
async def list_users(db: DBSession, limit: int = 100, offset: int = 0) -> list[UserPublic]:
    rows = (
        await db.execute(
            select(User).where(User.deleted_at.is_(None)).limit(limit).offset(offset)
        )
    ).scalars().all()
    return [UserPublic.model_validate(u) for u in rows]


@router.post(
    "/users/{user_id}/suspend",
    response_model=UserPublic,
    dependencies=[Depends(require_permissions("users.suspend"))],
)
async def suspend_user(
    user_id: UUID, request: Request, db: DBSession, actor: CurrentUser
) -> UserPublic:
    target = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    await _assert_not_super_admin(db, target)

    previous = {"status": target.status}
    target.status = "suspended"
    await db.flush()
    await AuditService.log(
        db,
        actor_user_id=actor.id,
        action="user.suspend",
        target_entity_type="user",
        target_entity_id=target.id,
        previous_value=previous,
        new_value={"status": "suspended"},
        ip_address=request.client.host if request.client else None,
    )
    return UserPublic.model_validate(target)


@router.post(
    "/users/{user_id}/activate",
    response_model=UserPublic,
    dependencies=[Depends(require_permissions("users.suspend"))],
)
async def activate_user(
    user_id: UUID, request: Request, db: DBSession, actor: CurrentUser
) -> UserPublic:
    target = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    previous = {"status": target.status}
    target.status = "active"
    await db.flush()
    await AuditService.log(
        db,
        actor_user_id=actor.id,
        action="user.activate",
        target_entity_type="user",
        target_entity_id=target.id,
        previous_value=previous,
        new_value={"status": "active"},
        ip_address=request.client.host if request.client else None,
    )
    return UserPublic.model_validate(target)


@router.post(
    "/users/{user_id}/roles/{role_name}",
    dependencies=[Depends(require_permissions("settings.manage"))],
)
async def assign_role(
    user_id: UUID,
    role_name: str,
    request: Request,
    db: DBSession,
    actor: CurrentUser,
) -> dict:
    """Super Admin only — grants a role to a user."""
    target = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    role = (await db.execute(select(Role).where(Role.name == role_name))).scalar_one_or_none()
    if role is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Role '{role_name}' not found")

    exists = (
        await db.execute(
            select(UserRole).where(UserRole.user_id == user_id, UserRole.role_id == role.id)
        )
    ).scalar_one_or_none()
    if exists:
        return {"status": "already_assigned", "role": role_name}

    db.add(UserRole(user_id=user_id, role_id=role.id))
    await db.flush()
    await AuditService.log(
        db,
        actor_user_id=actor.id,
        action="user.role_grant",
        target_entity_type="user",
        target_entity_id=user_id,
        previous_value=None,
        new_value={"role": role_name},
        ip_address=request.client.host if request.client else None,
    )
    return {"status": "granted", "role": role_name}


@router.delete(
    "/users/{user_id}/roles/{role_name}",
    dependencies=[Depends(require_permissions("settings.manage"))],
)
async def revoke_role(
    user_id: UUID,
    role_name: str,
    request: Request,
    db: DBSession,
    actor: CurrentUser,
) -> dict:
    """Super Admin only."""
    role = (await db.execute(select(Role).where(Role.name == role_name))).scalar_one_or_none()
    if role is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Role '{role_name}' not found")
    link = (
        await db.execute(
            select(UserRole).where(UserRole.user_id == user_id, UserRole.role_id == role.id)
        )
    ).scalar_one_or_none()
    if link is None:
        return {"status": "not_assigned"}

    await db.delete(link)
    await db.flush()
    await AuditService.log(
        db,
        actor_user_id=actor.id,
        action="user.role_revoke",
        target_entity_type="user",
        target_entity_id=user_id,
        previous_value={"role": role_name},
        new_value=None,
        ip_address=request.client.host if request.client else None,
    )
    return {"status": "revoked", "role": role_name}


# ==================================================================
# Audit logs — read only
# ==================================================================
@router.get(
    "/audit-logs",
    dependencies=[Depends(require_permissions("audit.view"))],
)
async def list_audit_logs(
    db: DBSession,
    action: str | None = None,
    actor_user_id: UUID | None = None,
    target_entity_type: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    stmt = select(AuditLog)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if actor_user_id:
        stmt = stmt.where(AuditLog.actor_user_id == actor_user_id)
    if target_entity_type:
        stmt = stmt.where(AuditLog.target_entity_type == target_entity_type)
    rows = (
        await db.execute(stmt.order_by(AuditLog.created_at.desc()).limit(limit).offset(offset))
    ).scalars().all()
    return [
        {
            "id": str(r.id),
            "actor_user_id": str(r.actor_user_id) if r.actor_user_id else None,
            "action": r.action,
            "target_entity_type": r.target_entity_type,
            "target_entity_id": str(r.target_entity_id) if r.target_entity_id else None,
            "previous_value": r.previous_value,
            "new_value": r.new_value,
            "ip_address": r.ip_address,
            "result": r.result,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]


# ==================================================================
# Helpers
# ==================================================================
async def _assert_not_super_admin(db: DBSession, target: User) -> None:
    perms = await get_user_permissions(db, target.id)
    if "settings.manage" in perms:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Plain admins cannot modify a Super Admin account",
        )