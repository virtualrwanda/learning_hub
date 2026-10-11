from functools import lru_cache

from app.services.payment.base import PaymentProvider, PaymentProviderError
from app.services.payment.momo import MomoProvider
from app.services.payment.paypal import PaypalProvider


@lru_cache
def _providers() -> dict[str, PaymentProvider]:
    return {"momo": MomoProvider(), "paypal": PaypalProvider()}


def get_provider(name: str) -> PaymentProvider:
    prov = _providers().get(name)
    if prov is None:
        raise PaymentProviderError(f"Unknown provider '{name}'")
    return prov