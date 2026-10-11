"""
Payment provider abstraction.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID


class PaymentProviderError(Exception):
    """Raised on any provider-side failure (network, config, declined, etc.)."""


@dataclass
class PaymentInitiateResult:
    provider_transaction_id: str
    status: str
    approval_url: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class PaymentWebhookEvent:
    provider_transaction_id: str
    status: str
    amount: float
    currency: str
    raw: dict[str, Any] = field(default_factory=dict)


class PaymentProvider(ABC):
    name: str

    @abstractmethod
    async def initiate(
        self,
        *,
        user_id: UUID,
        amount: float,
        currency: str,
        description: str,
        metadata: dict[str, Any],
        phone: str | None = None,
    ) -> PaymentInitiateResult:
        ...

    @abstractmethod
    async def verify_webhook(
        self,
        *,
        raw_body: bytes,
        headers: dict[str, str],
    ) -> PaymentWebhookEvent:
        ...