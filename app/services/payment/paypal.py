"""PayPal provider (mock by default)."""
import base64
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


class PaypalProvider(PaymentProvider):
    name = "paypal"

    async def _get_access_token(self) -> str:
        creds = f"{_settings.paypal_client_id}:{_settings.paypal_client_secret}"
        b64 = base64.b64encode(creds.encode()).decode()
        url = f"{_settings.paypal_base_url}/v1/oauth2/token"
        headers = {
            "Authorization": f"Basic {b64}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.post(
                url, headers=headers, data={"grant_type": "client_credentials"}
            )
            if r.status_code != 200:
                raise PaymentProviderError(
                    f"PayPal auth failed: {r.status_code} {r.text}"
                )
            return r.json()["access_token"]

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
        if _settings.paypal_mock:
            reference = f"mock_paypal_{uuid.uuid4().hex[:16]}"
            approval = (
                f"/api/v1/payments/paypal/mock/complete?reference={reference}"
                f"&outcome=success"
            )
            return PaymentInitiateResult(
                provider_transaction_id=reference,
                status="pending",
                approval_url=approval,
                raw={"mode": "mock", "amount": f"{amount:.2f}", "currency": currency},
            )

        if not (_settings.paypal_client_id and _settings.paypal_client_secret):
            raise PaymentProviderError("PayPal credentials missing")

        token = await self._get_access_token()
        url = f"{_settings.paypal_base_url}/v2/checkout/orders"
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        payload = {
            "intent": "CAPTURE",
            "purchase_units": [
                {
                    "reference_id": str(user_id),
                    "description": description[:127],
                    "amount": {"currency_code": currency, "value": f"{amount:.2f}"},
                }
            ],
            "application_context": {
                "return_url": "http://localhost:3000/payment/success",
                "cancel_url": "http://localhost:3000/payment/cancel",
                "user_action": "PAY_NOW",
                "brand_name": "Customized Learning Hub",
            },
        }
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.post(url, headers=headers, json=payload)
            if r.status_code not in (200, 201):
                raise PaymentProviderError(
                    f"PayPal order failed: {r.status_code} {r.text}"
                )
            data = r.json()

        order_id = data["id"]
        approval = next(
            (link["href"] for link in data.get("links", []) if link["rel"] == "approve"),
            None,
        )
        return PaymentInitiateResult(
            provider_transaction_id=order_id,
            status="pending",
            approval_url=approval,
            raw={"mode": "live", "order": data},
        )

    async def verify_webhook(
        self,
        *,
        raw_body: bytes,
        headers: dict[str, str],
    ) -> PaymentWebhookEvent:
        if _settings.paypal_mock:
            data = json.loads(raw_body.decode("utf-8"))
            return PaymentWebhookEvent(
                provider_transaction_id=data["reference"],
                status=data.get("status", "succeeded"),
                amount=float(data.get("amount", 0)),
                currency=data.get("currency", _settings.paypal_currency),
                raw=data,
            )

        if not _settings.paypal_webhook_id:
            raise PaymentProviderError("PAYPAL_WEBHOOK_ID not set")

        token = await self._get_access_token()
        verify_url = (
            f"{_settings.paypal_base_url}/v1/notifications/verify-webhook-signature"
        )
        verify_payload = {
            "transmission_id": headers.get("paypal-transmission-id"),
            "transmission_time": headers.get("paypal-transmission-time"),
            "cert_url": headers.get("paypal-cert-url"),
            "auth_algo": headers.get("paypal-auth-algo"),
            "transmission_sig": headers.get("paypal-transmission-sig"),
            "webhook_id": _settings.paypal_webhook_id,
            "webhook_event": json.loads(raw_body.decode("utf-8")),
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.post(
                verify_url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json=verify_payload,
            )
            if r.status_code != 200 or r.json().get("verification_status") != "SUCCESS":
                raise PaymentProviderError("PayPal webhook signature verification failed")

        data = verify_payload["webhook_event"]
        event_type = data.get("event_type", "")
        resource = data.get("resource", {})
        order_id = resource.get("id") or (
            resource.get("supplementary_data", {}).get("related_ids", {}).get("order_id")
        )
        amount_obj = resource.get("amount") or (
            resource.get("purchase_units", [{}])[0].get("amount", {})
        )

        if event_type in ("CHECKOUT.ORDER.APPROVED", "PAYMENT.CAPTURE.COMPLETED"):
            normalized = "succeeded"
        elif event_type in ("PAYMENT.CAPTURE.DENIED", "PAYMENT.CAPTURE.REVERSED"):
            normalized = "failed" if "DENIED" in event_type else "refunded"
        else:
            normalized = "pending"

        return PaymentWebhookEvent(
            provider_transaction_id=order_id or "unknown",
            status=normalized,
            amount=float(amount_obj.get("value", 0) or 0),
            currency=amount_obj.get("currency_code", _settings.paypal_currency),
            raw=data,
        )