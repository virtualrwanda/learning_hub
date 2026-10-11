from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


ProviderLiteral = Literal["momo", "paypal"]


class PaymentInitiateRequest(BaseModel):
    plan_id: UUID
    provider: ProviderLiteral
    # For MoMo only — the MSISDN (phone) to push to.
    phone: str | None = Field(default=None, max_length=32)


class PaymentInitiateResponse(BaseModel):
    transaction_id: UUID
    provider: str
    status: str
    # Provider-specific next step:
    #  - MoMo: "check your phone, approve the push"
    #  - PayPal: approval_url the user must open
    next_action: str
    provider_reference: str | None = None
    approval_url: str | None = None


class PaymentTransactionPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    subscription_id: UUID | None
    provider: str
    provider_transaction_id: str
    amount: float
    currency: str
    status: str
    created_at: datetime
    updated_at: datetime


class PaymentTransactionDetail(PaymentTransactionPublic):
    raw_payload: dict[str, Any] | None = None


class RefundRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=500)
    amount: float | None = Field(default=None, gt=0)