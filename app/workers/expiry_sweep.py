"""Background: expire subscriptions periodically."""
import asyncio
import logging

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.services.subscription_service import SubscriptionService

logger = logging.getLogger("clh.worker.expiry")
_settings = get_settings()


async def _sweep_once() -> dict[str, int]:
    async with AsyncSessionLocal() as db:
        try:
            result = await SubscriptionService.sweep_expirations(db)
            await db.commit()
            return result
        except Exception:
            await db.rollback()
            raise


async def run_forever(stop_event: asyncio.Event) -> None:
    logger.info(
        "Expiry sweep worker started (interval=%ss)",
        _settings.expiry_sweep_interval_seconds,
    )
    while not stop_event.is_set():
        try:
            counts = await _sweep_once()
            if counts["expired"] or counts["expiring_soon"]:
                logger.info(
                    "Sweep: %s expired, %s expiring soon",
                    counts["expired"], counts["expiring_soon"],
                )
        except Exception:
            logger.exception("Expiry sweep failed — will retry next interval")

        try:
            await asyncio.wait_for(
                stop_event.wait(), timeout=_settings.expiry_sweep_interval_seconds
            )
        except asyncio.TimeoutError:
            pass
    logger.info("Expiry sweep worker stopped")