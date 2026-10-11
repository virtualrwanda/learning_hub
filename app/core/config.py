from functools import lru_cache
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False
    )

    app_name: str = "Customized Learning Hub"
    env: str = "development"
    api_v1_prefix: str = "/api/v1"

    database_url: str
    database_url_sync: str
    redis_url: str

    session_ttl_seconds: int = 60 * 60 * 24 * 7
    session_cookie_name: str = "clh_session"
    session_cookie_secure: bool = False
    session_cookie_samesite: str = "lax"

    argon2_time_cost: int = 3
    argon2_memory_cost: int = 65536
    argon2_parallelism: int = 2

    email_verification_ttl_seconds: int = 86400
    password_reset_ttl_seconds: int = 3600

    default_subscription_price_usd: float = 25.0
    default_subscription_duration_days: int = 30
    default_notification_schedule: list[int] = Field(default_factory=lambda: [25, 20, 0])

    cors_origins: str = "http://localhost:3000"

    # --- Payment: MoMo ---
    momo_mock: bool = True
    momo_base_url: str = "https://sandbox.momodeveloper.mtn.com"
    momo_subscription_key: str = ""
    momo_api_user: str = ""
    momo_api_key: str = ""
    momo_target_environment: str = "sandbox"
    momo_callback_url: str = "http://localhost:8000/api/v1/payments/momo/webhook"
    momo_currency: str = "EUR"

    # --- Payment: PayPal ---
    paypal_mock: bool = True
    paypal_base_url: str = "https://api-m.sandbox.paypal.com"
    paypal_client_id: str = ""
    paypal_client_secret: str = ""
    paypal_webhook_id: str = ""
    paypal_currency: str = "USD"

    # --- Workers ---
    expiry_sweep_interval_seconds: int = 3600

    @field_validator("default_notification_schedule", mode="before")
    @classmethod
    def _parse_schedule(cls, v: Any) -> Any:
        if isinstance(v, str):
            import json

            return json.loads(v)
        return v

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.env.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]