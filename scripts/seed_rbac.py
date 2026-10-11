"""
Seed roles, permissions, role->permission mappings, and default system settings.

Run: python -m scripts.seed_rbac
Idempotent — safe to re-run any time.
"""
import asyncio

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.rbac import Permission, Role, RolePermission
from app.models.system_settings import SystemSetting

PERMISSIONS: list[tuple[str, str]] = [
    ("content.view", "View published content"),
    ("content.create", "Create content in the curriculum hierarchy"),
    ("content.publish", "Publish/unpublish content"),
    ("content.delete", "Archive or soft-delete content"),
    ("videos.manage", "Upload and manage video resources"),
    ("videos.download_policy", "Change video download policy"),
    ("documents.manage", "Upload and manage document resources"),
    ("users.view", "View user accounts"),
    ("users.suspend", "Suspend/reactivate user accounts"),
    ("users.delete", "Soft-delete user accounts"),
    ("payments.view", "View payment transactions"),
    ("payments.refund", "Issue refunds"),
    ("subscriptions.manage", "Activate, extend, suspend, cancel subscriptions"),
    ("settings.manage", "Manage system settings"),
    ("audit.view", "View audit logs"),
    ("reports.view", "View and export reports"),
    ("tutor.profile.manage", "Manage own tutor profile and CV"),
    ("tutor.approve", "Approve or reject tutor profiles"),
]

ROLE_MATRIX: dict[str, list[str]] = {
    "super_admin": [k for k, _ in PERMISSIONS],
    "admin": [k for k, _ in PERMISSIONS if k != "settings.manage"],
    "content_manager": [
        "content.view",
        "content.create",
        "content.publish",
        "content.delete",
        "videos.manage",
        "videos.download_policy",
        "documents.manage",
    ],
    "student": ["content.view"],
    "parent": ["reports.view"],
    "tutor": ["content.view", "tutor.profile.manage"],
}

DEFAULT_SETTINGS: dict[str, dict] = {
    "subscription.price_usd": {"value": 25.0, "is_public": True},
    "subscription.duration_days": {"value": 30, "is_public": True},
    "subscription.currency": {"value": "USD", "is_public": True},
    "notification.schedule_days_before_expiry": {"value": [25, 20, 0], "is_public": False},
    "download.default_policy": {"value": "disabled", "is_public": False},
}


async def _seed_permissions(db) -> dict[str, Permission]:
    mapping: dict[str, Permission] = {}
    for key, desc in PERMISSIONS:
        existing = (
            await db.execute(select(Permission).where(Permission.key == key))
        ).scalar_one_or_none()
        if not existing:
            existing = Permission(key=key, description=desc)
            db.add(existing)
            await db.flush()
        mapping[key] = existing
    return mapping


async def _seed_roles(db, perm_map: dict[str, Permission]) -> None:
    for role_name, perm_keys in ROLE_MATRIX.items():
        role = (
            await db.execute(select(Role).where(Role.name == role_name))
        ).scalar_one_or_none()
        if not role:
            role = Role(
                name=role_name,
                description=role_name.replace("_", " ").title(),
            )
            db.add(role)
            await db.flush()

        existing_links = set(
            (
                await db.execute(
                    select(RolePermission.permission_id).where(
                        RolePermission.role_id == role.id
                    )
                )
            ).scalars().all()
        )
        for key in perm_keys:
            pid = perm_map[key].id
            if pid not in existing_links:
                db.add(RolePermission(role_id=role.id, permission_id=pid))


async def _seed_settings(db) -> None:
    for key, cfg in DEFAULT_SETTINGS.items():
        existing = (
            await db.execute(select(SystemSetting).where(SystemSetting.key == key))
        ).scalar_one_or_none()
        if not existing:
            db.add(
                SystemSetting(key=key, value=cfg["value"], is_public=cfg["is_public"])
            )


async def main() -> None:
    async with AsyncSessionLocal() as db:
        perm_map = await _seed_permissions(db)
        await _seed_roles(db, perm_map)
        await _seed_settings(db)
        await db.commit()
    print("OK: RBAC + system settings seeded")


if __name__ == "__main__":
    asyncio.run(main())