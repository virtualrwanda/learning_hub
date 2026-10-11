"""
Subscription state machine + admin actions.

Blueprint Section 22. States: pending, active, expiring_soon, expired,
suspended, cancelled, payment_failed, manually_activated.

Every admin action writes an audit_logs entry with previous/new value.
"""
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.subscription import Subscription, SubscriptionPlan
from app.services.audit_service import AuditService

# Business rule (blueprint): renewal before expiry extends from prior end_date,
# avoiding lost paid time.
RENEWAL_EXTENDS_FROM_PRIOR = True


class SubscriptionService:
    # ------------------------------------------------------------------
    # Plans
    # ------------------------------------------------------------------
    @staticmethod
    async def get_active_plan(db: AsyncSession, plan_id: UUID) -> SubscriptionPlan:
        plan = (
            await db.execute(
                select(SubscriptionPlan).where(
                    SubscriptionPlan.id == plan_id,
                    SubscriptionPlan.is_active.is_(True),
                )
            )
        ).scalar_one_or_none()
        if plan is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Plan not found or inactive")
        return plan

    # ------------------------------------------------------------------
    # Student-facing
    # ------------------------------------------------------------------
    @staticmethod
    async def get_or_create_pending(
        db: AsyncSession, user_id: UUID, plan_id: UUID
    ) -> Subscription:
        existing = (
            await db.execute(
                select(Subscription).where(
                    Subscription.user_id == user_id,
                    Subscription.plan_id == plan_id,
                    Subscription.status == "pending",
                )
            )
        ).scalar_one_or_none()
        if existing:
            return existing
        sub = Subscription(user_id=user_id, plan_id=plan_id, status="pending")
        db.add(sub)
        await db.flush()
        return sub

    @staticmethod
    async def get_active_for_user(db: AsyncSession, user_id: UUID) -> Subscription | None:
        now = datetime.now(timezone.utc)
        return (
            await db.execute(
                select(Subscription)
                .where(
                    Subscription.user_id == user_id,
                    Subscription.status.in_(("active", "expiring_soon", "manually_activated")),
                    Subscription.end_date.is_not(None),
                    Subscription.end_date > now,
                )
                .order_by(Subscription.end_date.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

    # ------------------------------------------------------------------
    # Activation (webhook path OR admin override)
    # ------------------------------------------------------------------
    @staticmethod
    async def activate_from_payment(
        db: AsyncSession,
        *,
        user_id: UUID,
        plan_id: UUID,
    ) -> Subscription:
        plan = await SubscriptionService.get_active_plan(db, plan_id)
        now = datetime.now(timezone.utc)
        duration = timedelta(days=plan.duration_days)

        active = await SubscriptionService.get_active_for_user(db, user_id)
        if active and RENEWAL_EXTENDS_FROM_PRIOR:
            active.end_date = active.end_date + duration
            active.status = "active"
            await db.flush()
            return active

        sub = Subscription(
            user_id=user_id,
            plan_id=plan.id,
            status="active",
            start_date=now,
            end_date=now + duration,
        )
        db.add(sub)
        await db.flush()
        return sub

    # ------------------------------------------------------------------
    # Admin actions — each writes an audit entry
    # ------------------------------------------------------------------
    @staticmethod
    async def admin_activate(
        db: AsyncSession,
        *,
        actor_user_id: UUID,
        subscription_id: UUID,
        duration_days: int | None,
        reason: str,
        ip_address: str | None,
    ) -> Subscription:
        sub = await SubscriptionService._get(db, subscription_id)
        previous = {
            "status": sub.status,
            "start_date": str(sub.start_date),
            "end_date": str(sub.end_date),
        }
        now = datetime.now(timezone.utc)

        days = duration_days
        if days is None and sub.plan_id is not None:
            plan = await SubscriptionService.get_active_plan(db, sub.plan_id)
            days = plan.duration_days
        if days is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "duration_days required (subscription has no plan)",
            )

        sub.status = "manually_activated"
        sub.start_date = now
        sub.end_date = now + timedelta(days=days)
        await db.flush()

        await AuditService.log(
            db,
            actor_user_id=actor_user_id,
            action="subscription.manual_activate",
            target_entity_type="subscription",
            target_entity_id=sub.id,
            previous_value=previous,
            new_value={
                "status": sub.status,
                "start_date": str(sub.start_date),
                "end_date": str(sub.end_date),
                "reason": reason,
            },
            ip_address=ip_address,
        )
        return sub

    @staticmethod
    async def admin_extend(
        db: AsyncSession,
        *,
        actor_user_id: UUID,
        subscription_id: UUID,
        days: int,
        reason: str,
        ip_address: str | None,
    ) -> Subscription:
        sub = await SubscriptionService._get(db, subscription_id)
        if sub.end_date is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Cannot extend a subscription without an end_date",
            )
        previous = {"end_date": str(sub.end_date)}
        sub.end_date = sub.end_date + timedelta(days=days)
        sub.status = "active"
        await db.flush()

        await AuditService.log(
            db,
            actor_user_id=actor_user_id,
            action="subscription.extend",
            target_entity_type="subscription",
            target_entity_id=sub.id,
            previous_value=previous,
            new_value={"end_date": str(sub.end_date), "days_added": days, "reason": reason},
            ip_address=ip_address,
        )
        return sub

    @staticmethod
    async def admin_suspend(
        db: AsyncSession,
        *,
        actor_user_id: UUID,
        subscription_id: UUID,
        reason: str,
        ip_address: str | None,
    ) -> Subscription:
        sub = await SubscriptionService._get(db, subscription_id)
        previous = {"status": sub.status}
        sub.status = "suspended"
        await db.flush()
        await AuditService.log(
            db,
            actor_user_id=actor_user_id,
            action="subscription.suspend",
            target_entity_type="subscription",
            target_entity_id=sub.id,
            previous_value=previous,
            new_value={"status": "suspended", "reason": reason},
            ip_address=ip_address,
        )
        return sub

    @staticmethod
    async def admin_cancel(
        db: AsyncSession,
        *,
        actor_user_id: UUID,
        subscription_id: UUID,
        reason: str,
        ip_address: str | None,
    ) -> Subscription:
        sub = await SubscriptionService._get(db, subscription_id)
        previous = {"status": sub.status}
        sub.status = "cancelled"
        await db.flush()
        await AuditService.log(
            db,
            actor_user_id=actor_user_id,
            action="subscription.cancel",
            target_entity_type="subscription",
            target_entity_id=sub.id,
            previous_value=previous,
            new_value={"status": "cancelled", "reason": reason},
            ip_address=ip_address,
        )
        return sub

    @staticmethod
    async def admin_set_expiry(
        db: AsyncSession,
        *,
        actor_user_id: UUID,
        subscription_id: UUID,
        end_date: datetime,
        reason: str,
        ip_address: str | None,
    ) -> Subscription:
        sub = await SubscriptionService._get(db, subscription_id)
        previous = {"end_date": str(sub.end_date)}
        sub.end_date = end_date
        await db.flush()
        await AuditService.log(
            db,
            actor_user_id=actor_user_id,
            action="subscription.set_expiry",
            target_entity_type="subscription",
            target_entity_id=sub.id,
            previous_value=previous,
            new_value={"end_date": str(end_date), "reason": reason},
            ip_address=ip_address,
        )
        return sub

    # ------------------------------------------------------------------
    # Expiry sweep — called by background worker
    # ------------------------------------------------------------------
    @staticmethod
    async def sweep_expirations(db: AsyncSession) -> dict[str, int]:
        now = datetime.now(timezone.utc)
        soon_cutoff = now + timedelta(days=3)

        to_expire = (
            await db.execute(
                select(Subscription).where(
                    Subscription.status.in_(("active", "expiring_soon", "manually_activated")),
                    Subscription.end_date.is_not(None),
                    Subscription.end_date < now,
                )
            )
        ).scalars().all()
        for s in to_expire:
            s.status = "expired"

        to_soon = (
            await db.execute(
                select(Subscription).where(
                    Subscription.status.in_(("active", "manually_activated")),
                    Subscription.end_date.is_not(None),
                    Subscription.end_date >= now,
                    Subscription.end_date <= soon_cutoff,
                )
            )
        ).scalars().all()
        for s in to_soon:
            s.status = "expiring_soon"

        await db.flush()
        return {"expired": len(to_expire), "expiring_soon": len(to_soon)}

    # ------------------------------------------------------------------
    @staticmethod
    async def _get(db: AsyncSession, subscription_id: UUID) -> Subscription:
        sub = (
            await db.execute(select(Subscription).where(Subscription.id == subscription_id))
        ).scalar_one_or_none()
        if sub is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Subscription not found")
        return sub