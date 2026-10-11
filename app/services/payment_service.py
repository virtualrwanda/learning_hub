"""
Payment orchestration — initiate + webhook processing.

Guarantees:
  - Activation happens ONLY from a verified webhook (or an admin override).
  - Duplicate webhooks are idempotent (unique constraint on provider_transaction_id).
  - Every state change is transactional and auditable.
"""
from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment import PaymentTransaction
from app.models.subscription import Subscription, SubscriptionPlan
from app.schemas.payment import PaymentInitiateResponse
from app.services.payment import get_provider
from app.services.payment.base import PaymentProviderError
from app.services.subscription_service import SubscriptionService

import logging

logger = logging.getLogger("clh.payment")


class PaymentService:
    @staticmethod
    async def initiate(
        db: AsyncSession,
        *,
        user_id: UUID,
        plan_id: UUID,
        provider_name: str,
        phone: str | None = None,
    ) -> PaymentInitiateResponse:
        plan = await SubscriptionService.get_active_plan(db, plan_id)
        provider = get_provider(provider_name)

        try:
            result = await provider.initiate(
                user_id=user_id,
                amount=float(plan.price_usd),
                currency="USD" if provider_name == "paypal" else "EUR",
                description=f"CLH subscription: {plan.name}",
                metadata={"plan_id": str(plan.id), "user_id": str(user_id)},
                phone=phone,
            )
        except PaymentProviderError as e:
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(e))

        # Persist the pending transaction
        tx = PaymentTransaction(
            user_id=user_id,
            subscription_id=None,
            provider=provider_name,
            provider_transaction_id=result.provider_transaction_id,
            amount=float(plan.price_usd),
            currency="USD" if provider_name == "paypal" else "EUR",
            status=result.status,
            raw_payload=result.raw,
        )
        db.add(tx)
        await db.flush()

        # Ensure a pending subscription record exists
        await SubscriptionService.get_or_create_pending(db, user_id, plan.id)

        return PaymentInitiateResponse(
            transaction_id=tx.id,
            provider=provider_name,
            status=result.status,
            next_action=(
                "Open the approval_url to approve payment"
                if result.approval_url
                else "Check your phone and approve the payment prompt"
            ),
            provider_reference=result.provider_transaction_id,
            approval_url=result.approval_url,
        )

    @staticmethod
    async def process_webhook(
        db: AsyncSession,
        *,
        provider_name: str,
        raw_body: bytes,
        headers: dict[str, str],
    ) -> dict:
        """
        Returns a small JSON-able summary. Providers that reach this path have
        already been through `verify_webhook` — the caller decides what to do
        with the summary.
        """
        provider = get_provider(provider_name)
        try:
            event = await provider.verify_webhook(raw_body=raw_body, headers=headers)
        except PaymentProviderError as e:
            logger.warning("Webhook verify failed for %s: %s", provider_name, e)
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Webhook verification failed: {e}")

        tx = (
            await db.execute(
                select(PaymentTransaction).where(
                    PaymentTransaction.provider_transaction_id == event.provider_transaction_id
                )
            )
        ).scalar_one_or_none()
        if tx is None:
            logger.warning("Webhook for unknown transaction %s", event.provider_transaction_id)
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown transaction reference")

        # Idempotency: if we already processed a terminal state, no-op.
        if tx.status in ("succeeded", "refunded") and event.status == tx.status:
            return {"status": "duplicate", "transaction_id": str(tx.id)}

        tx.status = event.status
        tx.raw_payload = {**(tx.raw_payload or {}), "webhook": event.raw}
        await db.flush()

        if event.status == "succeeded":
            # Locate the plan via the pending subscription or the tx payload
            sub = (
                await db.execute(
                    select(Subscription)
                    .where(
                        Subscription.user_id == tx.user_id,
                        Subscription.status == "pending",
                    )
                    .order_by(Subscription.created_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()

            plan_id = None
            if sub and sub.plan_id:
                plan_id = sub.plan_id
            else:
                # Fallback: read from raw_payload metadata
                meta = (tx.raw_payload or {}).get("metadata") or {}
                if meta.get("plan_id"):
                    plan_id = UUID(meta["plan_id"])

            if plan_id is None:
                logger.error("Webhook success but no plan_id found for tx %s", tx.id)
                raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Cannot determine plan")

            active_sub = await SubscriptionService.activate_from_payment(
                db, user_id=tx.user_id, plan_id=plan_id
            )
            tx.subscription_id = active_sub.id

            # Clean up orphaned pending row (we merged into the active one)
            if sub and sub.id != active_sub.id:
                sub.status = "cancelled"

            await db.flush()
            logger.info(
                "Payment succeeded: user=%s plan=%s end_date=%s",
                tx.user_id, plan_id, active_sub.end_date,
            )
            return {"status": "activated", "subscription_id": str(active_sub.id)}

        if event.status == "failed":
            logger.info("Payment failed: tx=%s", tx.id)
            return {"status": "failed"}

        return {"status": "recorded"}