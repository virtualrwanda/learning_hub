from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.core.deps import (
    CurrentUser,
    DBSession,
    get_user_permissions,
    require_permissions,
)
from app.models.user import User
from app.schemas.user import UserPublic, UserUpdateSelf

router = APIRouter(prefix="/users", tags=["users"])


@router.get(
    "",
    response_model=list[UserPublic],
    dependencies=[Depends(require_permissions("users.view"))],
)
async def list_users(db: DBSession, limit: int = 50, offset: int = 0) -> list[UserPublic]:
    rows = (
        await db.execute(
            select(User).where(User.deleted_at.is_(None)).limit(limit).offset(offset)
        )
    ).scalars().all()
    return [UserPublic.model_validate(u) for u in rows]


@router.get("/{user_id}", response_model=UserPublic)
async def get_user(user_id: UUID, db: DBSession, me: CurrentUser) -> UserPublic:
    if user_id != me.id:
        perms = await get_user_permissions(db, me.id)
        if "users.view" not in perms:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Forbidden")
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return UserPublic.model_validate(user)


@router.patch("/me", response_model=UserPublic)
async def update_me(payload: UserUpdateSelf, db: DBSession, me: CurrentUser) -> UserPublic:
    data = payload.model_dump(exclude_unset=True)
    if "grade_id" in data:
        me.current_grade_id = data.pop("grade_id")
    for field, value in data.items():
        setattr(me, field, value)
    await db.flush()
    return UserPublic.model_validate(me)