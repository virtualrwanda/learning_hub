"""MTN MoMo provider (mock by default)."""
import json
import uuid
from typing import Any

import httpx

from app.core.config import get_settings
from app.services.payment.base import (
    PaymentInitiateResult,
    PaymentProvider,
    PaymentProviderError,
    PaymentWebhookEvent,
)

_settings = get_settings()


class MomoProvider(PaymentProvider):
    name = "momo"

    async def initiate(
        self,
        *,
        user_id,
        amount: float,
        currency: str,
        description: str,
        metadata: dict[str, Any],
        phone: str | None = None,
    ) -> PaymentInitiateResult:
        if _settings.momo_mock:
            return await self._mock_initiate(
                user_id=user_id, amount=amount, currency=currency, phone=phone
            )
        if not phone:
            raise PaymentProviderError("MoMo requires a phone number (MSISDN)")
        if not (
            _settings.momo_subscription_key
            and _settings.momo_api_user
            and _settings.momo_api_key
        ):
            raise PaymentProviderError("MoMo credentials missing")

        reference = str(uuid.uuid4())
        url = f"{_settings.momo_base_url}/collection/v1_0/requesttopay"
        headers = {
            "Authorization": f"Bearer {_settings.momo_api_key}",
            "X-Reference-Id": reference,
            "X-Target-Environment": _settings.momo_target_environment,
            "Ocp-Apim-Subscription-Key": _settings.momo_subscription_key,
            "Content-Type": "application/json",
        }
        payload = {
            "amount": f"{amount:.2f}",
            "currency": currency,
            "externalId": str(user_id),
            "payer": {"partyIdType": "MSISDN", "partyId": phone},
            "payerMessage": description[:255],
            "payeeNote": "CLH subscription",
        }
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                r = await client.post(url, headers=headers, json=payload)
                if r.status_code not in (200, 202):
                    raise PaymentProviderError(
                        f"MoMo initiate failed: {r.status_code} {r.text}"
                    )
        except httpx.HTTPError as e:
            raise PaymentProviderError(f"MoMo network error: {e}") from e

        return PaymentInitiateResult(
            provider_transaction_id=reference,
            status="pending",
            approval_url=None,
            raw={"mode": "live", "request_status": r.status_code},
        )

    async def _mock_initiate(
        self, *, user_id, amount, currency, phone
    ) -> PaymentInitiateResult:
        reference = f"mock_momo_{uuid.uuid4().hex[:16]}"
        return PaymentInitiateResult(
            provider_transaction_id=reference,
            status="pending",
            approval_url=(
                f"/api/v1/payments/momo/mock/complete?reference={reference}"
                f"&outcome=success"
            ),
            raw={
                "mode": "mock",
                "user_id": str(user_id),
                "amount": f"{amount:.2f}",
                "currency": currency,
                "phone": phone,
            },
        )

    async def verify_webhook(
        self,
        *,
        raw_body: bytes,
        headers: dict[str, str],
    ) -> PaymentWebhookEvent:
        if _settings.momo_mock:
            data = json.loads(raw_body.decode("utf-8"))
            return PaymentWebhookEvent(
                provider_transaction_id=data["reference"],
                status=data.get("status", "succeeded"),
                amount=float(data.get("amount", 0)),
                currency=data.get("currency", _settings.momo_currency),
                raw=data,
            )

        try:
            data = json.loads(raw_body.decode("utf-8"))
        except Exception as e:
            raise PaymentProviderError(f"Invalid MoMo webhook body: {e}") from e
        reference = data.get("referenceId") or data.get("externalId")
        if not reference:
            raise PaymentProviderError("MoMo webhook missing referenceId")

        url = f"{_settings.momo_base_url}/collection/v1_0/requesttopay/{reference}"
        headers_get = {
            "Authorization": f"Bearer {_settings.momo_api_key}",
            "X-Target-Environment": _settings.momo_target_environment,
            "Ocp-Apim-Subscription-Key": _settings.momo_subscription_key,
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(url, headers=headers_get)
            if r.status_code != 200:
                raise PaymentProviderError(f"MoMo status verify failed: {r.status_code}")
            status_data = r.json()

        raw_status = status_data.get("status", "").upper()
        normalized = {
            "SUCCESSFUL": "succeeded",
            "FAILED": "failed",
            "PENDING": "pending",
        }.get(raw_status, "pending")

        return PaymentWebhookEvent(
            provider_transaction_id=reference,
            status=normalized,
            amount=float(status_data.get("amount", 0)),
            currency=status_data.get("currency", _settings.momo_currency),
            raw=status_data,
        )