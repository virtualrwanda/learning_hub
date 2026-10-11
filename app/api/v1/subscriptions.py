"""
Subscription routes.

  - Plans:  public read, admin/super_admin write
  - Student: view own subscription + history, create pending, choose plan
  - Admin:  list all, manual activate, extend, suspend, cancel, set expiry

Every admin action writes an audit_logs row (via SubscriptionService).
All endpoints return objects that were `refresh()`-ed after write, so
Pydantic can read server-defaulted columns without MissingGreenlet.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select

from app.core.deps import CurrentUser, DBSession, require_permissions
from app.models.subscription import Subscription, SubscriptionPlan
from app.schemas.subscription import (
    SubscriptionCancel,
    SubscriptionCreate,
    SubscriptionExtend,
    SubscriptionManualActivate,
    SubscriptionPlanCreate,
    SubscriptionPlanPublic,
    SubscriptionPlanUpdate,
    SubscriptionPublic,
    SubscriptionSetExpiry,
    SubscriptionSuspend,
)
from app.services.subscription_service import SubscriptionService

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


# ==================================================================
# Plans (public read, admin write)
# ==================================================================
@router.get("/plans", response_model=list[SubscriptionPlanPublic])
async def list_plans(db: DBSession, _user: CurrentUser) -> list[SubscriptionPlanPublic]:
    rows = (
        await db.execute(
            select(SubscriptionPlan)
            .where(SubscriptionPlan.is_active.is_(True))
            .order_by(SubscriptionPlan.price_usd)
        )
    ).scalars().all()
    return [SubscriptionPlanPublic.model_validate(r) for r in rows]


@router.post(
    "/plans",
    response_model=SubscriptionPlanPublic,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions("subscriptions.manage"))],
)
async def create_plan(
    payload: SubscriptionPlanCreate, db: DBSession
) -> SubscriptionPlanPublic:
    existing = (
        await db.execute(
            select(SubscriptionPlan).where(SubscriptionPlan.name == payload.name)
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "Plan name already exists")

    plan = SubscriptionPlan(**payload.model_dump())
    db.add(plan)
    await db.flush()
    await db.refresh(plan)
    return SubscriptionPlanPublic.model_validate(plan)


@router.patch(
    "/plans/{plan_id}",
    response_model=SubscriptionPlanPublic,
    dependencies=[Depends(require_permissions("subscriptions.manage"))],
)
async def update_plan(
    plan_id: UUID, payload: SubscriptionPlanUpdate, db: DBSession
) -> SubscriptionPlanPublic:
    plan = (
        await db.execute(
            select(SubscriptionPlan).where(SubscriptionPlan.id == plan_id)
        )
    ).scalar_one_or_none()
    if plan is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Plan not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(plan, field, value)
    await db.flush()
    await db.refresh(plan)
    return SubscriptionPlanPublic.model_validate(plan)


# ==================================================================
# Student
# ==================================================================
@router.get("/me", response_model=SubscriptionPublic | None)
async def my_subscription(
    db: DBSession, user: CurrentUser
) -> SubscriptionPublic | None:
    sub = await SubscriptionService.get_active_for_user(db, user.id)
    return SubscriptionPublic.model_validate(sub) if sub else None


@router.get("/me/history", response_model=list[SubscriptionPublic])
async def my_subscription_history(
    db: DBSession, user: CurrentUser
) -> list[SubscriptionPublic]:
    rows = (
        await db.execute(
            select(Subscription)
            .where(Subscription.user_id == user.id)
            .order_by(Subscription.created_at.desc())
        )
    ).scalars().all()
    return [SubscriptionPublic.model_validate(r) for r in rows]


@router.post(
    "/pending",
    response_model=SubscriptionPublic,
    status_code=status.HTTP_201_CREATED,
)
async def create_pending(
    payload: SubscriptionCreate, db: DBSession, user: CurrentUser
) -> SubscriptionPublic:
    sub = await SubscriptionService.get_or_create_pending(
        db, user.id, payload.plan_id
    )
    await db.flush()
    await db.refresh(sub)
    return SubscriptionPublic.model_validate(sub)


# ==================================================================
# Admin
# ==================================================================
@router.get(
    "",
    response_model=list[SubscriptionPublic],
    dependencies=[Depends(require_permissions("subscriptions.manage"))],
)
async def list_all(
    db: DBSession,
    status_filter: str | None = Query(default=None, alias="status"),
    user_id: UUID | None = Query(default=None),
    limit: int = Query(default=100, le=500),
    offset: int = 0,
) -> list[SubscriptionPublic]:
    stmt = select(Subscription)
    if status_filter:
        stmt = stmt.where(Subscription.status == status_filter)
    if user_id:
        stmt = stmt.where(Subscription.user_id == user_id)
    rows = (
        await db.execute(
            stmt.order_by(Subscription.created_at.desc()).limit(limit).offset(offset)
        )
    ).scalars().all()
    return [SubscriptionPublic.model_validate(r) for r in rows]


@router.get(
    "/{subscription_id}",
    response_model=SubscriptionPublic,
    dependencies=[Depends(require_permissions("subscriptions.manage"))],
)
async def get_one(
    subscription_id: UUID, db: DBSession
) -> SubscriptionPublic:
    sub = await SubscriptionService._get(db, subscription_id)
    return SubscriptionPublic.model_validate(sub)


@router.post(
    "/{subscription_id}/activate",
    response_model=SubscriptionPublic,
    dependencies=[Depends(require_permissions("subscriptions.manage"))],
)
async def admin_activate(
    subscription_id: UUID,
    payload: SubscriptionManualActivate,
    request: Request,
    db: DBSession,
    user: CurrentUser,
) -> SubscriptionPublic:
    sub = await SubscriptionService.admin_activate(
        db,
        actor_user_id=user.id,
        subscription_id=subscription_id,
        duration_days=payload.duration_days,
        reason=payload.reason,
        ip_address=request.client.host if request.client else None,
    )
    await db.refresh(sub)
    return SubscriptionPublic.model_validate(sub)


@router.post(
    "/{subscription_id}/extend",
    response_model=SubscriptionPublic,
    dependencies=[Depends(require_permissions("subscriptions.manage"))],
)
async def admin_extend(
    subscription_id: UUID,
    payload: SubscriptionExtend,
    request: Request,
    db: DBSession,
    user: CurrentUser,
) -> SubscriptionPublic:
    sub = await SubscriptionService.admin_extend(
        db,
        actor_user_id=user.id,
        subscription_id=subscription_id,
        days=payload.days,
        reason=payload.reason,
        ip_address=request.client.host if request.client else None,
    )
    await db.refresh(sub)
    return SubscriptionPublic.model_validate(sub)


@router.post(
    "/{subscription_id}/suspend",
    response_model=SubscriptionPublic,
    dependencies=[Depends(require_permissions("subscriptions.manage"))],
)
async def admin_suspend(
    subscription_id: UUID,
    payload: SubscriptionSuspend,
    request: Request,
    db: DBSession,
    user: CurrentUser,
) -> SubscriptionPublic:
    sub = await SubscriptionService.admin_suspend(
        db,
        actor_user_id=user.id,
        subscription_id=subscription_id,
        reason=payload.reason,
        ip_address=request.client.host if request.client else None,
    )
    await db.refresh(sub)
    return SubscriptionPublic.model_validate(sub)


@router.post(
    "/{subscription_id}/cancel",
    response_model=SubscriptionPublic,
    dependencies=[Depends(require_permissions("subscriptions.manage"))],
)
async def admin_cancel(
    subscription_id: UUID,
    payload: SubscriptionCancel,
    request: Request,
    db: DBSession,
    user: CurrentUser,
) -> SubscriptionPublic:
    sub = await SubscriptionService.admin_cancel(
        db,
        actor_user_id=user.id,
        subscription_id=subscription_id,
        reason=payload.reason,
        ip_address=request.client.host if request.client else None,
    )
    await db.refresh(sub)
    return SubscriptionPublic.model_validate(sub)


@router.post(
    "/{subscription_id}/set-expiry",
    response_model=SubscriptionPublic,
    dependencies=[Depends(require_permissions("subscriptions.manage"))],
)
async def admin_set_expiry(
    subscription_id: UUID,
    payload: SubscriptionSetExpiry,
    request: Request,
    db: DBSession,
    user: CurrentUser,
) -> SubscriptionPublic:
    sub = await SubscriptionService.admin_set_expiry(
        db,
        actor_user_id=user.id,
        subscription_id=subscription_id,
        end_date=payload.end_date,
        reason=payload.reason,
        ip_address=request.client.host if request.client else None,
    )
    await db.refresh(sub)
    return SubscriptionPublic.model_validate(sub)