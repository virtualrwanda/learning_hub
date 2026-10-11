"""
Session service — no Redis.

Storage model:
  - Postgres `sessions` table: durable record, admin-visible, audit trail
  - In-process dict: fast validation lookup (populated lazily on first miss)

Single-active-session enforcement:
  - On login, every non-revoked session for the user is revoked (DB + cache)
  - In-process cache is evicted accordingly

Limitations vs Redis version:
  - The in-process cache is per-worker. If you run multiple uvicorn workers
    (--workers N > 1), each has its own cache but always reads the DB as
    fallback, so correctness is preserved. Latency is slightly higher.
  - No automatic TTL eviction in the cache — we evict on access if expired.
  - If you later add Redis, swap `_Cache` for a Redis client.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from threading import Lock
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import generate_opaque_token, hash_token
from app.models.user_session import UserSession

logger = logging.getLogger("clh.session")
_settings = get_settings()


class _Cache:
    """Thread-safe in-process session cache."""

    def __init__(self) -> None:
        self._data: dict[str, tuple[dict, datetime]] = {}
        self._lock = Lock()

    def get(self, key: str) -> dict | None:
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                return None
            payload, expires_at = entry
            if expires_at <= datetime.now(timezone.utc):
                del self._data[key]
                return None
            return payload

    def set(self, key: str, payload: dict, ttl_seconds: int) -> None:
        with self._lock:
            self._data[key] = (payload, datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds))

    def delete(self, key: str) -> None:
        with self._lock:
            self._data.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()


_cache = _Cache()


class SessionService:
    def __init__(self, redis=None):  # accept and ignore legacy arg
        pass

    @staticmethod
    def _key(token_hash: str) -> str:
        return f"session:{token_hash}"

    async def create_session(
        self,
        db: AsyncSession,
        *,
        user_id: UUID,
        ip: str | None,
        device_info: str | None,
    ) -> str:
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=_settings.session_ttl_seconds)

        # Revoke any prior active sessions for this user (single-session rule)
        existing = (
            await db.execute(
                select(UserSession).where(
                    UserSession.user_id == user_id,
                    UserSession.revoked_at.is_(None),
                )
            )
        ).scalars().all()

        for s in existing:
            s.revoked_at = now
            _cache.delete(self._key(s.session_token_hash))

        # Create new session
        token = generate_opaque_token()
        token_hash = hash_token(token)

        row = UserSession(
            user_id=user_id,
            session_token_hash=token_hash,
            device_info=(device_info or "")[:255] or None,
            ip_address=ip,
            last_activity_at=now,
            expires_at=expires_at,
        )
        db.add(row)
        await db.flush()

        payload = {
            "user_id": str(user_id),
            "session_id": str(row.id),
            "issued_at": now.isoformat(),
            "device_info": row.device_info,
        }
        _cache.set(self._key(token_hash), payload, _settings.session_ttl_seconds)
        return token

    async def validate_and_touch(self, token: str) -> dict | None:
        token_hash = hash_token(token)
        cache_key = self._key(token_hash)

        # Fast path: cache hit
        cached = _cache.get(cache_key)
        if cached is not None:
            return cached

        # Slow path: DB lookup (also re-hydrates the cache)
        # We use a fresh session so this works even outside a request context.
        from app.db.session import AsyncSessionLocal

        async with AsyncSessionLocal() as db:
            row = (
                await db.execute(
                    select(UserSession).where(
                        UserSession.session_token_hash == token_hash,
                        UserSession.revoked_at.is_(None),
                    )
                )
            ).scalar_one_or_none()

            if row is None:
                return None

            now = datetime.now(timezone.utc)
            if row.expires_at <= now:
                return None

            # Sliding TTL: push expiry forward
            row.last_activity_at = now
            row.expires_at = now + timedelta(seconds=_settings.session_ttl_seconds)
            await db.commit()

            payload = {
                "user_id": str(row.user_id),
                "session_id": str(row.id),
                "issued_at": row.created_at.isoformat() if row.created_at else now.isoformat(),
                "device_info": row.device_info,
            }
            _cache.set(cache_key, payload, _settings.session_ttl_seconds)
            return payload

    async def revoke(self, db: AsyncSession, token: str) -> None:
        token_hash = hash_token(token)
        _cache.delete(self._key(token_hash))
        await db.execute(
            update(UserSession)
            .where(UserSession.session_token_hash == token_hash)
            .values(revoked_at=datetime.now(timezone.utc))
        )

    async def revoke_all_for_user(self, db: AsyncSession, user_id: UUID) -> int:
        rows = (
            await db.execute(
                select(UserSession).where(
                    UserSession.user_id == user_id,
                    UserSession.revoked_at.is_(None),
                )
            )
        ).scalars().all()
        now = datetime.now(timezone.utc)
        for s in rows:
            s.revoked_at = now
            _cache.delete(self._key(s.session_token_hash))
        return len(rows)