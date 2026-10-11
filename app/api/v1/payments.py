"""
Payment routes:
  - Student initiates a payment (MoMo or PayPal)
  - Webhooks from providers (never trust the client)
  - Mock helpers for local testing when MOMO_MOCK / PAYPAL_MOCK is true
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select

from app.core.config import get_settings
from app.core.deps import CurrentUser, DBSession, require_permissions
from app.models.payment import PaymentTransaction
from app.schemas.payment import (
    PaymentInitiateRequest,
    PaymentInitiateResponse,
    PaymentTransactionDetail,
    PaymentTransactionPublic,
    RefundRequest,
)
from app.services.audit_service import AuditService
from app.services.payment_service import PaymentService

router = APIRouter(prefix="/payments", tags=["payments"])
_settings = get_settings()


# ==================================================================
# Initiation
# ==================================================================
@router.post("/initiate", response_model=PaymentInitiateResponse)
async def initiate(
    payload: PaymentInitiateRequest,
    db: DBSession,
    user: CurrentUser,
) -> PaymentInitiateResponse:
    if payload.provider == "momo" and not payload.phone:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "MoMo requires `phone`")
    return await PaymentService.initiate(
        db,
        user_id=user.id,
        plan_id=payload.plan_id,
        provider_name=payload.provider,
        phone=payload.phone,
    )


# ==================================================================
# User-facing listing
# ==================================================================
@router.get("/me", response_model=list[PaymentTransactionPublic])
async def my_payments(db: DBSession, user: CurrentUser) -> list[PaymentTransactionPublic]:
    rows = (
        await db.execute(
            select(PaymentTransaction)
            .where(PaymentTransaction.user_id == user.id)
            .order_by(PaymentTransaction.created_at.desc())
        )
    ).scalars().all()
    return [PaymentTransactionPublic.model_validate(r) for r in rows]


# ==================================================================
# Webhooks
# ==================================================================
@router.post("/momo/webhook", include_in_schema=False)
async def momo_webhook(request: Request, db: DBSession) -> dict:
    raw = await request.body()
    headers = {k.lower(): v for k, v in request.headers.items()}
    return await PaymentService.process_webhook(
        db, provider_name="momo", raw_body=raw, headers=headers
    )


@router.post("/paypal/webhook", include_in_schema=False)
async def paypal_webhook(request: Request, db: DBSession) -> dict:
    raw = await request.body()
    headers = {k.lower(): v for k, v in request.headers.items()}
    return await PaymentService.process_webhook(
        db, provider_name="paypal", raw_body=raw, headers=headers
    )


# ==================================================================
# Mock helpers — only live when MOCK flags are on
# ==================================================================
@router.post("/momo/mock/complete", include_in_schema=False)
async def momo_mock_complete(
    reference: str = Query(...),
    outcome: str = Query(default="success"),
    db: DBSession = None,  # injected
) -> dict:
    if not _settings.momo_mock:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Mock mode disabled")
    payload = {
        "reference": reference,
        "status": "succeeded" if outcome == "success" else "failed",
        "amount": 25.0,
        "currency": _settings.momo_currency,
    }
    import json
    return await PaymentService.process_webhook(
        db, provider_name="momo", raw_body=json.dumps(payload).encode(), headers={}
    )


@router.post("/paypal/mock/complete", include_in_schema=False)
async def paypal_mock_complete(
    reference: str = Query(...),
    outcome: str = Query(default="success"),
    db: DBSession = None,
) -> dict:
    if not _settings.paypal_mock:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Mock mode disabled")
    payload = {
        "reference": reference,
        "status": "succeeded" if outcome == "success" else "failed",
        "amount": 25.0,
        "currency": _settings.paypal_currency,
    }
    import json
    return await PaymentService.process_webhook(
        db, provider_name="paypal", raw_body=json.dumps(payload).encode(), headers={}
    )


# ==================================================================
# Admin
# ==================================================================
@router.get(
    "",
    response_model=list[PaymentTransactionPublic],
    dependencies=[Depends(require_permissions("payments.view"))],
)
async def list_payments(
    db: DBSession,
    provider: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    user_id: UUID | None = Query(default=None),
    limit: int = Query(default=100, le=500),
    offset: int = 0,
) -> list[PaymentTransactionPublic]:
    stmt = select(PaymentTransaction)
    if provider:
        stmt = stmt.where(PaymentTransaction.provider == provider)
    if status_filter:
        stmt = stmt.where(PaymentTransaction.status == status_filter)
    if user_id:
        stmt = stmt.where(PaymentTransaction.user_id == user_id)
    rows = (
        await db.execute(
            stmt.order_by(PaymentTransaction.created_at.desc()).limit(limit).offset(offset)
        )
    ).scalars().all()
    return [PaymentTransactionPublic.model_validate(r) for r in rows]


@router.get(
    "/{payment_id}",
    response_model=PaymentTransactionDetail,
    dependencies=[Depends(require_permissions("payments.view"))],
)
async def get_payment(payment_id: UUID, db: DBSession) -> PaymentTransactionDetail:
    tx = (
        await db.execute(select(PaymentTransaction).where(PaymentTransaction.id == payment_id))
    ).scalar_one_or_none()
    if tx is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Payment not found")
    return PaymentTransactionDetail.model_validate(tx)


@router.post(
    "/{payment_id}/refund",
    response_model=PaymentTransactionPublic,
    dependencies=[Depends(require_permissions("payments.refund"))],
)
async def refund_payment(
    payment_id: UUID,
    payload: RefundRequest,
    request: Request,
    db: DBSession,
    user: CurrentUser,
) -> PaymentTransactionPublic:
    tx = (
        await db.execute(select(PaymentTransaction).where(PaymentTransaction.id == payment_id))
    ).scalar_one_or_none()
    if tx is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Payment not found")
    if tx.status != "succeeded":
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Only successful payments can be refunded"
        )

    previous = {"status": tx.status}
    tx.status = "refunded"
    await db.flush()

    await AuditService.log(
        db,
        actor_user_id=user.id,
        action="payment.refund",
        target_entity_type="payment_transaction",
        target_entity_id=tx.id,
        previous_value=previous,
        new_value={
            "status": "refunded",
            "amount": payload.amount or float(tx.amount),
            "reason": payload.reason,
        },
        ip_address=request.client.host if request.client else None,
    )
    return PaymentTransactionPublic.model_validate(tx)