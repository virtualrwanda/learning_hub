"""
Redis has been removed for this deployment.

Sessions are now stored in the Postgres `sessions` table + an in-process dict
(see SessionService). This module exists only to satisfy imports that may
still reference `get_redis` / `close_redis` and can be deleted once nothing
imports it.

If you later deploy with Redis (production multi-instance), restore the
original `from redis.asyncio import from_url` implementation and set the
REDIS_URL env var.
"""
from __future__ import annotations

import logging

logger = logging.getLogger("clh.redis_stub")


async def get_redis():  # type: ignore[no-untyped-def]
    """Return None — no Redis available."""
    return None


async def close_redis() -> None:
    """No-op."""
    logger.debug("close_redis() called (no Redis configured)")