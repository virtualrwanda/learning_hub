"""
Shared helpers for content hierarchy CRUD.

The hierarchy is: curricula → grades → subjects → courses → units → lessons.
Each level has a FK to the one above it, publish flag (where relevant), and
soft-delete via `deleted_at`.

Important: `apply_update()` calls `db.refresh(obj)` after flush so that
server-defaulted columns (updated_at, created_at) are available on the
in-memory object before Pydantic serializes it.
"""
from datetime import datetime, timezone
from typing import Any, TypeVar
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base

T = TypeVar("T", bound=Base)


async def get_or_404(db: AsyncSession, model: type[T], pk: UUID) -> T:
    """Fetch a non-deleted row by primary key, or raise 404."""
    obj = (
        await db.execute(
            select(model).where(model.id == pk, model.deleted_at.is_(None))
        )
    ).scalar_one_or_none()
    if obj is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, f"{model.__name__} not found"
        )
    return obj


async def apply_update(db: AsyncSession, obj: Any, payload: dict) -> Any:
    """
    Apply a partial update from a Pydantic model_dump(exclude_unset=True).

    We call `db.refresh(obj)` after flush so that any server-defaulted columns
    (e.g. `updated_at = func.now()`) are populated on the in-memory object
    before the caller serializes it with Pydantic.

    Without the refresh, Pydantic raises MissingGreenlet when it tries to read
    a column that SQLAlchemy hasn't loaded yet.
    """
    for field, value in payload.items():
        setattr(obj, field, value)
    await db.flush()
    await db.refresh(obj)
    return obj


async def soft_delete(db: AsyncSession, obj: Any) -> None:
    """Mark an object deleted without removing the row (preserves FK integrity)."""
    obj.deleted_at = datetime.now(timezone.utc)
    await db.flush()


async def reorder_items(db: AsyncSession, items: list, ids: list[UUID]) -> None:
    """
    Assigns `order_index` in the given order. Items not present in `ids` keep
    their current order_index. New indexes start at 0.
    """
    by_id = {item.id: item for item in items}
    for idx, item_id in enumerate(ids):
        item = by_id.get(item_id)
        if item is not None:
            item.order_index = idx
    await db.flush()


async def ensure_unique_name(
    db: AsyncSession,
    model: type[T],
    field: str,
    value: str,
    *,
    exclude_id: UUID | None = None,
) -> None:
    """
    Enforce uniqueness on a (model, field) combination at the application
    layer — portable across databases (MySQL in dev, Postgres in prod).
    """
    stmt = select(model).where(
        getattr(model, field) == value, model.deleted_at.is_(None)
    )
    if exclude_id is not None:
        stmt = stmt.where(model.id != exclude_id)
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"{model.__name__} with {field}='{value}' already exists",
        )